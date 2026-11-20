"""動作確認用のサンプル wav を作る（Karplus-Strong 法で弦をはじいた音を合成）。

    python scripts/make_sample.py samples/sample.wav

鳴らす音（MIDI 番号）は SEQUENCE にあり、タブ譜の答え合わせに使える。
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 22050
# (開始秒, 長さ秒, [MIDI ノート])。単音のメロディのあと E メジャーの和音
SEQUENCE = [
    (0.0, 0.45, [52]),  # E3
    (0.5, 0.45, [55]),  # G3
    (1.0, 0.45, [57]),  # A3
    (1.5, 0.45, [59]),  # B3
    (2.0, 0.45, [62]),  # D4
    (2.5, 0.45, [64]),  # E4
    (3.0, 0.45, [67]),  # G4
    (3.5, 0.45, [69]),  # A4
    (4.0, 1.5, [40, 47, 52, 56, 59, 64]),  # E メジャー（開放）
]


def pluck(midi: int, seconds: float, rng: np.random.Generator) -> np.ndarray:
    freq = 440.0 * 2 ** ((midi - 69) / 12)
    period = int(round(SR / freq))
    buf = rng.uniform(-1, 1, period)
    out = np.empty(int(SR * seconds))
    for i in range(len(out)):
        out[i] = buf[i % period]
        buf[i % period] = 0.996 * 0.5 * (buf[i % period] + buf[(i + 1) % period])
    return out


def main(path: str) -> None:
    rng = np.random.default_rng(0)
    total = max(s + d for s, d, _ in SEQUENCE) + 0.5
    audio = np.zeros(int(SR * total))
    for start, dur, notes in SEQUENCE:
        for k, midi in enumerate(notes):
            # 和音はストロークっぽく少しずつずらす
            i = int(SR * (start + 0.008 * k))
            tone = pluck(midi, dur, rng)
            audio[i : i + len(tone)] += tone
    audio /= np.max(np.abs(audio)) * 1.1
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "samples/sample.wav")
