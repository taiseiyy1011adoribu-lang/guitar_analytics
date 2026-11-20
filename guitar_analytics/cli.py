"""コマンドライン: wav を渡すと ASCII タブ譜を出す。

    python -m guitar_analytics input.wav [-o out.txt]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fingering import assign_frets
from .rhythm import estimate_beats, group_timed_events, make_grid, quantize
from .tab import render_rhythm_tab, render_tab
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
    parser.add_argument("--bpm", type=float, help="テンポを指定する（省略時は音源から推定）")
    parser.add_argument("--beats-per-bar", type=int, default=4, help="1 小節の拍数（4 なら 4/4 拍子）")
    parser.add_argument("--no-rhythm", action="store_true", help="リズムを付けず、弾く順番だけを並べる")
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
    if args.no_rhythm:
        events = group_events(notes, tolerance=args.chord_ms / 1000.0)
        positions = assign_frets([pitches for _, pitches in events])
        text = render_tab(positions, width=args.width)
    else:
        timed = group_timed_events(notes, tolerance=args.chord_ms / 1000.0)
        bpm, beats = estimate_beats(args.audio)
        if args.bpm:
            bpm, beats = args.bpm, []
        grid = make_grid(bpm, beats, timed[0].start if timed else 0.0)
        qevents = quantize(timed, grid)
        positions = assign_frets([q.pitches for q in qevents])
        text = render_rhythm_tab(
            positions,
            [q.step for q in qevents],
            [q.length for q in qevents],
            steps_per_bar=args.beats_per_bar * 4,
            width=args.width,
            header=f"テンポ {bpm:.0f} BPM / {args.beats_per_bar} 拍子"
            "（音価: w=全 h=2分 q=4分 e=8分 s=16分 .=付点）",
        )

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"{len(notes)} 音を検出し、{args.output} に書き出しました", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
