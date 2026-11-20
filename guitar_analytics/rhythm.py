"""テンポを推定し、ノートの開始・長さを 16 分音符のグリッドにそろえる。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .transcribe import Note

STEPS_PER_BEAT = 4  # 1 拍（4 分音符）を 16 分音符 4 つに分ける

# 16 分音符いくつ分か → 音価の記号（w=全, h=2分, q=4分, e=8分, s=16分, . は付点）
DURATION_SYMBOLS = {16: "w", 12: "h.", 8: "h", 6: "q.", 4: "q", 3: "e.", 2: "e", 1: "s"}


@dataclass(frozen=True)
class Grid:
    bpm: float
    offset: float  # 1 小節目の頭の時刻（秒）

    @property
    def step_seconds(self) -> float:
        return 60.0 / self.bpm / STEPS_PER_BEAT

    def to_step(self, seconds: float) -> int:
        return round((seconds - self.offset) / self.step_seconds)


@dataclass(frozen=True)
class TimedEvent:
    start: float
    end: float
    pitches: list[int]


def estimate_beats(audio_path: str | Path) -> tuple[float, list[float]]:
    """librosa のビート検出で (BPM, 拍の時刻のリスト) を返す。"""
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    bpm = float(np.atleast_1d(tempo)[0])
    if len(beats) >= 4:
        # beat_track の BPM は粗いので、拍の時刻に直線を当てはめて間隔を求め直す
        period = float(np.polyfit(np.arange(len(beats)), beats, 1)[0])
        if period > 0:
            bpm = 60.0 / period
    return bpm, [float(b) for b in beats]


def make_grid(bpm: float, beats: list[float], first_onset: float) -> Grid:
    """最初の音にいちばん近い拍を 1 小節目の頭とするグリッドを作る。

    ビート検出の拍がなければ、最初の音をそのまま頭にする。
    """
    if not beats:
        return Grid(bpm, first_onset)
    beat = 60.0 / bpm
    # 検出された拍の位相に合わせて、最初の音の近くまで拍をさかのぼる・進める
    anchor = beats[0] + round((first_onset - beats[0]) / beat) * beat
    return Grid(bpm, anchor)


def group_timed_events(notes: list[Note], tolerance: float = 0.05) -> list[TimedEvent]:
    """開始が tolerance 秒以内の音を 1 イベントにまとめ、終わりは一番長い音に合わせる。"""
    events: list[TimedEvent] = []
    for n in notes:
        if events and n.start - events[-1].start <= tolerance:
            last = events[-1]
            pitches = last.pitches if n.pitch in last.pitches else last.pitches + [n.pitch]
            events[-1] = TimedEvent(last.start, max(last.end, n.end), pitches)
        else:
            events.append(TimedEvent(n.start, n.end, [n.pitch]))
    return events


@dataclass(frozen=True)
class QuantizedEvent:
    step: int  # 1 小節目の頭から数えた 16 分音符の位置
    length: int  # 16 分音符いくつ分鳴っているか（1 以上）
    pitches: list[int]


def quantize(events: list[TimedEvent], grid: Grid) -> list[QuantizedEvent]:
    """各イベントをグリッドに乗せる。

    同じ位置に来たイベントは 1 つにまとめる。長さは基本的に次の音までの間隔とし、
    音が間隔の半分も鳴っていなければ（休符をはさむとみなして）音そのものの長さにする。
    """
    placed: list[tuple[int, int, list[int]]] = []
    for ev in events:
        step = max(0, grid.to_step(ev.start))
        end_step = max(step + 1, grid.to_step(ev.end))
        if placed and placed[-1][0] == step:
            prev_step, prev_end, prev_pitches = placed[-1]
            merged = prev_pitches + [p for p in ev.pitches if p not in prev_pitches]
            placed[-1] = (prev_step, max(prev_end, end_step), merged)
        else:
            placed.append((step, end_step, list(ev.pitches)))

    result = []
    for i, (step, end_step, pitches) in enumerate(placed):
        if i + 1 < len(placed):
            gap = placed[i + 1][0] - step
            end_step = step + gap if end_step - step >= gap / 2 else min(end_step, step + gap)
        result.append(QuantizedEvent(step, max(1, end_step - step), pitches))
    return result


def duration_symbol(length: int, steps_left_in_bar: int) -> str:
    """16 分音符 length 個分を、小節の残りに収まる一番近い音価の記号にする。"""
    length = max(1, min(length, steps_left_in_bar))
    best = max(k for k in DURATION_SYMBOLS if k <= length)
    return DURATION_SYMBOLS[best]
