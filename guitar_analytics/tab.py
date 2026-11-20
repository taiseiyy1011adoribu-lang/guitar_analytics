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
