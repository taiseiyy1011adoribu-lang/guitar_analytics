"""単純ルール（毎回いちばん低いフレット）とビタビの比較。

    python examples/compare_fingering.py
"""
from guitar_analytics.fingering import (
    assign_frets_naive, assign_positions, hand_travel, to_ascii_tab, total_cost,
)

EXAMPLES = {
    "Aマイナーペンタの上昇・下降フレーズ": [
        [69], [72], [74], [76], [79], [76], [74], [72], [69], [67], [64],
    ],
    "Am → F → C のコードとメロディ": [
        [57, 64, 69, 72], [72], [71], [69],
        [53, 60, 65, 69], [69], [67], [65],
        [48, 55, 60, 64], [64], [67], [72],
    ],
    "高音域のメロディ": [
        [76], [78], [79], [81], [83], [81], [79], [78], [76],
    ],
}

for title, events in EXAMPLES.items():
    naive = assign_frets_naive(events)
    smart = assign_positions(events)
    print(f"=== {title} ===")
    print(f"--- 単純ルール  コスト {total_cost(naive):6.1f} / 手の移動 {hand_travel(naive):3d} フレット")
    print(to_ascii_tab(naive))
    print(f"--- ビタビ      コスト {total_cost(smart):6.1f} / 手の移動 {hand_travel(smart):3d} フレット")
    print(to_ascii_tab(smart))
    print()
