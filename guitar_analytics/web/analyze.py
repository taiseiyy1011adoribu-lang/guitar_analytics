"""音声ファイルを解析して、画面に渡す JSON 用の dict を作る。

弦・フレット割り当てとタブ譜の文字列化は既存のモジュールをそのまま使う。
より賢い割り当て（guitar_analytics.fingering）があればそちらを優先する。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..tab import render_tab
from ..theory import analyze_theory
from ..transcribe import Note, drop_harmonics, group_events, transcribe

try:  # 別の作業で追加される予定の割り当て。無ければ単純版を使う
    from ..fingering import assign_frets  # type: ignore[import-not-found]

    FINGERING = "fingering"
except ImportError:
    from ..simple_fingering import assign_frets

    FINGERING = "simple_fingering"


@dataclass
class Options:
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    min_note_ms: float = 100.0
    chord_ms: float = 50.0
    keep_harmonics: bool = False

    @classmethod
    def from_query(cls, query: dict[str, list[str]]) -> "Options":
        opts = cls()
        for name in ("onset_threshold", "frame_threshold", "min_note_ms", "chord_ms"):
            if name in query:
                setattr(opts, name, float(query[name][0]))
        if "keep_harmonics" in query:
            opts.keep_harmonics = query["keep_harmonics"][0] in ("1", "true", "on")
        return opts


def analyze(audio_path: str | Path, opts: Options | None = None) -> dict:
    opts = opts or Options()
    notes = transcribe(
        audio_path,
        onset_threshold=opts.onset_threshold,
        frame_threshold=opts.frame_threshold,
        min_note_ms=opts.min_note_ms,
    )
    return build_result(notes, opts)


def build_result(notes: list[Note], opts: Options | None = None) -> dict:
    """ノート列から画面用の結果を作る（Basic Pitch を通さないのでテストしやすい）。"""
    opts = opts or Options()
    all_notes = notes
    kept = notes if opts.keep_harmonics else drop_harmonics(notes)
    kept_ids = {id(n) for n in kept}

    events = group_events(kept, tolerance=opts.chord_ms / 1000.0)
    positions = assign_frets([pitches for _, pitches in events])

    # イベント内のノートに、元のノートの長さと信頼度を対応づける
    out_events = []
    pending = sorted(kept, key=lambda n: (n.start, n.pitch))
    for (time, pitches), pos in zip(events, positions):
        members = []
        for pitch, p in zip(pitches, pos):
            note = _take(pending, pitch, time, opts.chord_ms / 1000.0)
            members.append(
                {
                    "pitch": pitch,
                    "string": p[0] if p else None,
                    "fret": p[1] if p else None,
                    "end": note.end if note else time + 0.25,
                    "velocity": note.velocity if note else None,
                }
            )
        out_events.append({"time": time, "notes": members})

    duration = max((n.end for n in all_notes), default=0.0)
    return {
        "duration": duration,
        "fingering": FINGERING,
        "notes": [
            {
                "start": n.start,
                "end": n.end,
                "pitch": n.pitch,
                "velocity": n.velocity,
                "dropped": id(n) not in kept_ids,
            }
            for n in all_notes
        ],
        "events": out_events,
        "ascii": render_tab(positions),
        # キー・スケール・コードの推定と、ソロ・アレンジの提案（音が少ないときは None）
        "theory": analyze_theory(kept),
    }


def _take(pending: list[Note], pitch: int, time: float, tol: float) -> Note | None:
    """イベントの音に対応する元のノートを取り出す（同じノートは 2 度使わない）。"""
    for i, n in enumerate(pending):
        if n.pitch == pitch and abs(n.start - time) <= tol + 1e-9:
            return pending.pop(i)
    return None
