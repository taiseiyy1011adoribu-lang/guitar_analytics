# guitar_analytics

## 弦・フレット割り当て（`guitar_analytics/fingering.py`）

同時に鳴る MIDI ノートのイベント列から、各ノートを弾く弦とフレットを
動的計画法（ビタビ）で選びます。

- 状態: 押さえ方（同時発音は必ず別弦、指 4 本以内、セーハ可）と手のポジション（人差し指のフレット、届く範囲は 4 フレット）
- 状態コスト: ストレッチ幅、高いポジション、開放弦ボーナス、和音の間の弾かない弦
- 遷移コスト: 手のポジション移動量、5 フレットを超えるシフト、単音での弦の飛び越し
- 重みは `CostWeights` で調整できます

```python
from guitar_analytics.fingering import assign_frets
assign_frets([[64], [62], [48, 52, 55, 60, 64]])
# => [[(1, 0)], [(2, 3)], [(5, 3), (4, 2), (3, 0), (2, 1), (1, 0)]]
```

単純ルール（毎回いちばん低いフレット）との比較: `PYTHONPATH=. python examples/compare_fingering.py`

テスト: `python -m pytest tests`
