# guitar_analytics

音源（wav など）からギターのタブ譜をテキストで作る最小版です。

1. [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) で音高・開始・終了のノート列を取り出す
2. 倍音を誤検出した弱い音を取り除き、ほぼ同時に始まる音を和音としてまとめる
3. 単純なルール（高い音から順に、空いている弦のうち一番低いフレット）で弦とフレットを決める
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

### 画面で見る

```sh
python -m guitar_analytics.web          # http://127.0.0.1:8000/ がブラウザで開く
python -m guitar_analytics.web --port 8080 --no-browser
```

音声ファイルをドロップすると、時間に沿ったタブ譜と検出した音のピアノロールが表示されます。
再生するとカーソルが動き、クリックした位置から再生できます。「聞く音」で元の音源と検出した音（簡単な合成音）を切り替えられるので、取りこぼしや誤検出を耳で確かめられます。
しきい値は「解析の設定」から変えて解析し直せます。追加のライブラリは要りません（Python 標準のサーバーで動きます）。

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

## テスト

```sh
pip install pytest
python -m pytest tests
```

## 今後

- 弦とフレットの割り当てを賢くする（`guitar_analytics/simple_fingering.py` の `assign_frets` と同じ形で差し替えられます）
- リズム（音の長さ）をタブ譜に反映する
