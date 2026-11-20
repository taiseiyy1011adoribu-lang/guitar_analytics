"""(弦, フレット) の列を ASCII タブ譜の文字列にする。"""
from __future__ import annotations

STRING_NAMES = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}


def render_tab(
    positions: list[list[tuple[int, int] | None]],
    width: int = 80,
) -> str:
    """1 イベントを 1 列として並べ、width 文字ごとに段を折り返す。"""
    columns: list[dict[int, str]] = []
    for event in positions:
        col = {s: str(f) for p in event if p is not None for s, f in [p]}
        if col:
            columns.append(col)

    blocks: list[str] = []
    line_body = {s: "" for s in STRING_NAMES}
    prefix_len = 3  # "e|-"
    for col in columns:
        cell = max(len(v) for v in col.values())
        if len(line_body[1]) + cell + 1 + prefix_len + 1 > width and line_body[1]:
            blocks.append(_block(line_body))
            line_body = {s: "" for s in STRING_NAMES}
        for s in STRING_NAMES:
            line_body[s] += col.get(s, "").ljust(cell, "-") + "-"
    if line_body[1] or not blocks:
        blocks.append(_block(line_body))
    return "\n\n".join(blocks) + "\n"


def _block(body: dict[int, str]) -> str:
    return "\n".join(f"{STRING_NAMES[s]}|-{body[s]}|" for s in STRING_NAMES)


def render_rhythm_tab(
    positions: list[list[tuple[int, int] | None]],
    steps: list[int],
    lengths: list[int],
    steps_per_bar: int = 16,
    width: int = 80,
    header: str | None = None,
) -> str:
    """16 分音符 1 つを一定の幅で並べ、小節線と音価の記号を付けたタブ譜にする。

    positions[i] の音は 16 分音符で steps[i] 番目に始まり、lengths[i] 個分鳴る。
    各段の上の行が音価（w h q e s、. は付点）。
    """
    from .rhythm import duration_symbol

    fret_width = max(
        (len(str(f)) for ev in positions for p in ev if p is not None for _, f in [p]),
        default=1,
    )
    cell = fret_width + 1
    n_bars = (max(steps, default=0) // steps_per_bar) + 1

    # 小節ごとに、各ステップの中身を作る
    bars: list[dict[int | str, str]] = [
        {key: "" for key in ["rhythm", *STRING_NAMES]} for _ in range(n_bars)
    ]
    cells: dict[int, tuple[list[tuple[int, int] | None], int]] = {}
    for pos, step, length in zip(positions, steps, lengths):
        cells[step] = (pos, length)

    for b in range(n_bars):
        bar = bars[b]
        for s in range(b * steps_per_bar, (b + 1) * steps_per_bar):
            pos, length = cells.get(s, ([], 0))
            frets = {st: str(f) for p in pos if p is not None for st, f in [p]}
            if frets:
                left = (b + 1) * steps_per_bar - s
                bar["rhythm"] += duration_symbol(length, left).ljust(cell)
            else:
                bar["rhythm"] += " " * cell
            for st in STRING_NAMES:
                bar[st] += frets.get(st, "").ljust(cell, "-")

    bar_len = steps_per_bar * cell + 1
    per_line = max(1, (width - 2) // bar_len)
    blocks = []
    for i in range(0, n_bars, per_line):
        chunk = bars[i : i + per_line]
        lines = ["  " + " ".join(bar["rhythm"] for bar in chunk).rstrip()]
        for st in STRING_NAMES:
            lines.append(f"{STRING_NAMES[st]}|" + "|".join(bar[st] for bar in chunk) + "|")
        blocks.append("\n".join(lines))
    text = "\n\n".join(blocks) + "\n"
    if header:
        text = header + "\n\n" + text
    return text
