# -*- mode: python ; coding: utf-8 -*-
# PyInstaller の設定。リポジトリの直下で次のように実行する:
#   pyinstaller packaging/guitar_analytics.spec --noconfirm
# dist/GuitarTab/ に exe と必要なファイル一式ができる。
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [("../guitar_analytics/web/static", "guitar_analytics/web/static")]
# Basic Pitch のモデル（ONNX）、resampy のフィルター、librosa の遅延読み込み用ファイル
for pkg in ("basic_pitch", "resampy", "librosa"):
    datas += collect_data_files(pkg)

hiddenimports = (
    ["pkg_resources"]
    + 
    collect_submodules("librosa")
    + ["onnxruntime", "pretty_midi", "mir_eval", "sklearn.utils._typedefs"]
)

a = Analysis(
    ["launcher.py"],
    pathex=[".."],
    datas=datas,
    hiddenimports=hiddenimports,
    # 使わない大きなライブラリは入れない（モデルは onnxruntime で動かす）
    excludes=["tensorflow", "coremltools", "tflite_runtime", "matplotlib", "tkinter", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GuitarTab",
    icon="icon.ico",
    console=True,  # 黒い画面を閉じればアプリが終わるようにする
)
coll = COLLECT(exe, a.binaries, a.datas, name="GuitarTab")
