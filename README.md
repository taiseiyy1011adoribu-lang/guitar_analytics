# guitar_analytics

音源（wav など）からギターのタブ譜をテキストで作る最小版です。

1. [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) で音高・開始・終了のノート列を取り出す
2. 倍音を誤検出した弱い音を取り除き、ほぼ同時に始まる音を和音としてまとめる
3. 動的計画法（ビタビ）で、手の移動が少なく弾きやすい弦とフレットを選ぶ（下の「弦・フレット割り当て」）
4. ASCII タブ譜として出力する

## セットアップ

Python 3.10 か 3.11 が必要です（Basic Pitch の都合）。

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 使い方

```sh
python -m guitar_analytics input.wav             # 標準出力にタブ譜
python -m guitar_analytics input.wav -o tab.txt  # ファイルに書き出す
python -m guitar_analytics input.wav --notes     # 検出したノートも表示
```

`pip install -e .` すると `guitar-tab input.wav` でも動きます。
主なオプションは `python -m guitar_analytics -h` を見てください。

## サンプル

`samples/sample.wav` は `scripts/make_sample.py` で合成した音（E3 から A4 までの単音 8 つと、開放の E メジャー和音）です。
出力は `samples/sample_tab.txt` にあります。

```
e|-----------0-3-5---|
B|-------0-3-------0-|
G|---0-2-----------1-|
D|-2-----------------|
A|-----------------2-|
E|-----------------0-|
```

単音はすべて正しく取れています。和音は 6 音のうち 4 音で、4 弦 2 フレット（E3）は 6 弦開放の倍音として、1 弦開放（E4）は Basic Pitch が検出しなかったため抜けています。

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

以前の単純ルールは `guitar_analytics/simple_fingering.py` に残してあります。

## テスト

```sh
pip install pytest
python -m pytest tests
```

## 今後

- リズム（音の長さ）をタブ譜に反映する
