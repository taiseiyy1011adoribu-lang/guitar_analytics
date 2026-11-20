"""コマンドライン: wav を渡すと ASCII タブ譜を出す。

    python -m guitar_analytics input.wav [-o out.txt]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .simple_fingering import assign_frets
from .tab import render_tab
from .transcribe import drop_harmonics, group_events, transcribe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guitar_analytics", description="音源（wav など）からギターのタブ譜を作る"
    )
    parser.add_argument("audio", type=Path, help="入力の音声ファイル")
    parser.add_argument("-o", "--output", type=Path, help="タブ譜の出力先（省略時は標準出力）")
    parser.add_argument("--onset-threshold", type=float, default=0.5, help="音の立ち上がり検出のしきい値")
    parser.add_argument("--frame-threshold", type=float, default=0.3, help="音が鳴っている判定のしきい値")
    parser.add_argument("--min-note-ms", type=float, default=100.0, help="これより短い音は捨てる（ミリ秒）")
    parser.add_argument("--chord-ms", type=float, default=50.0, help="この時間内に始まる音を和音とみなす（ミリ秒）")
    parser.add_argument("--keep-harmonics", action="store_true", help="倍音らしき弱い音を消さずに残す")
    parser.add_argument("--notes", action="store_true", help="検出したノート一覧も標準エラーに出す")
    parser.add_argument("--width", type=int, default=80, help="1 段の最大文字数")
    args = parser.parse_args(argv)

    if not args.audio.exists():
        parser.error(f"ファイルが見つかりません: {args.audio}")

    notes = transcribe(
        args.audio,
        onset_threshold=args.onset_threshold,
        frame_threshold=args.frame_threshold,
        min_note_ms=args.min_note_ms,
    )
    if not args.keep_harmonics:
        notes = drop_harmonics(notes)
    if args.notes:
        for n in notes:
            print(f"{n.start:7.3f}-{n.end:7.3f}s  pitch={n.pitch:3d}  conf={n.velocity:.2f}", file=sys.stderr)
    events = group_events(notes, tolerance=args.chord_ms / 1000.0)
    positions = assign_frets([pitches for _, pitches in events])
    text = render_tab(positions, width=args.width)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"{len(notes)} 音を検出し、{args.output} に書き出しました", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
