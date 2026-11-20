"""Basic Pitch で音声ファイルからノート列を取り出す。"""
from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Note:
    start: float  # 秒
    end: float  # 秒
    pitch: int  # MIDI ノート番号
    velocity: float  # 0〜1 の信頼度


def transcribe(
    audio_path: str | Path,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_ms: float = 100.0,
) -> list[Note]:
    """wav などの音声から、開始時刻順に並んだノート列を返す。"""
    # Basic Pitch（と TensorFlow）の import は重いので呼ばれたときだけ読む
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    # predict は進捗を標準出力に書くので、タブ譜と混ざらないよう標準エラーへ回す
    with contextlib.redirect_stdout(sys.stderr):
        _, _, note_events = predict(
            str(audio_path),
            ICASSP_2022_MODEL_PATH,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_ms,
            # ギターの音域（E2 ≒ 82Hz 〜 20 フレットの C6 ≒ 1047Hz）に絞る
            minimum_frequency=75.0,
            maximum_frequency=1100.0,
        )
    notes = [Note(float(s), float(e), int(p), float(a)) for s, e, p, a, _ in note_events]
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


HARMONIC_INTERVALS = (12, 19, 24)  # 2 倍音・3 倍音・4 倍音にあたる音程（半音）


def drop_harmonics(notes: list[Note], ratio: float = 1.5) -> list[Note]:
    """倍音を別の音と誤検出したものを取り除く。

    ある音のオクターブ上などに、時間が重なっていて信頼度が ratio 倍以上弱い音が
    あれば、それは倍音とみなして捨てる。
    """
    kept = []
    for n in notes:
        is_harmonic = any(
            n.pitch - other.pitch in HARMONIC_INTERVALS
            and other.start <= n.start + 0.05
            and other.end > n.start
            and other.velocity >= n.velocity * ratio
            for other in notes
        )
        if not is_harmonic:
            kept.append(n)
    return kept


def group_events(notes: list[Note], tolerance: float = 0.05) -> list[tuple[float, list[int]]]:
    """開始時刻が tolerance 秒以内のノートを同時に鳴る 1 イベントにまとめる。

    戻り値は (開始時刻, MIDI ノート番号のリスト) の列。
    """
    events: list[tuple[float, list[int]]] = []
    for note in notes:
        if events and note.start - events[-1][0] <= tolerance:
            if note.pitch not in events[-1][1]:
                events[-1][1].append(note.pitch)
        else:
            events.append((note.start, [note.pitch]))
    return events
