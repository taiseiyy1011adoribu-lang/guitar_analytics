"""検出したノート列から、キー・スケール・コード進行を推定し、ソロやアレンジの手がかりを作る。

Basic Pitch や librosa に依存しない純粋な Python なので、テストや別の画面からも使える。

- estimate_key:     音の長さと強さで重みを付けた 12 音のヒストグラムを、
                    Krumhansl-Kessler のキー・プロファイルと相関させて 24 のキーを順位付け
- rank_scales:      ペンタトニックやモードを含む 10 種類 × 12 ルートのスケールを順位付け
- estimate_chords:  短い時間窓ごとにコードの型と照合し、ビタビで頻繁な切り替わりを抑える
- analyze_theory:   上の 3 つと、ソロ・アレンジの提案をまとめて画面用の dict にする
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Protocol


class NoteLike(Protocol):
    start: float
    end: float
    pitch: int
    velocity: float


SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
# 調号がフラットになるメジャーキー（F, B♭, E♭, A♭, D♭, G♭）のルート
FLAT_MAJOR_ROOTS = {5, 10, 3, 8, 1, 6}

KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

MAJOR_IV = (0, 2, 4, 5, 7, 9, 11)
MINOR_IV = (0, 2, 3, 5, 7, 8, 10)


@dataclass(frozen=True)
class Scale:
    id: str
    ja: str
    en: str
    intervals: tuple[int, ...]
    mode: str  # "major" か "minor"（明るい側か暗い側か）
    prior: float  # よく使われるスケールを少し優先する
    desc: str
    solo_tip: str


SCALES: list[Scale] = [
    Scale("major", "メジャー", "Major (Ionian)", MAJOR_IV, "major", 0.06,
          "明るく安定した響き。いわゆるドレミファソラシです。",
          "メロディを歌うように。4度と7度は経過音にして、1・3・5度で落ち着かせると安定します。"),
    Scale("minor", "ナチュラルマイナー", "Natural Minor (Aeolian)", MINOR_IV, "minor", 0.06,
          "暗く切ない響き。3度・6度・7度が半音下がっています。",
          "マイナーペンタに 2度と♭6度を足した形。♭6度を伸ばすと泣きのフレーズになります。"),
    Scale("minpent", "マイナーペンタトニック", "Minor Pentatonic", (0, 3, 5, 7, 10), "minor", 0.05,
          "ロックやブルースのソロの基本になる 5 音。半音の並びがなく外れにくいです。",
          "まず覚えるならこれ。ルートの箱（第 1 ポジション）でチョーキング（♭3→3、4→5）を使うと一気にそれらしくなります。"),
    Scale("majpent", "メジャーペンタトニック", "Major Pentatonic", (0, 2, 4, 7, 9), "major", 0.04,
          "メジャースケールから 4度と7度を抜いた 5 音。明るく素朴な響きです。",
          "カントリーやポップス向き。2度から3度へのチョーキングやハンマリングが定番です。"),
    Scale("blues", "ブルーススケール", "Blues", (0, 3, 5, 6, 7, 10), "minor", 0.02,
          "マイナーペンタに♭5（ブルーノート）を足したもの。",
          "♭5 は止まらずに 4→♭5→5 と通過させるとブルースらしくなります。"),
    Scale("dorian", "ドリアン", "Dorian", (0, 2, 3, 5, 7, 9, 10), "minor", 0.0,
          "マイナーの仲間で、6度だけ半音高い。少し明るくおしゃれな響きです。",
          "マイナーペンタに 2度と 6度を足した形。6度を強調するとファンクやフュージョンっぽくなります。"),
    Scale("mixo", "ミクソリディアン", "Mixolydian", (0, 2, 4, 5, 7, 9, 10), "major", 0.0,
          "メジャーの仲間で、7度が半音低い（♭7）。ロックンロールの響きです。",
          "メジャーペンタに 4度と♭7度を足した形。♭7 を混ぜるとブルージーなメジャーになります。"),
    Scale("harm", "ハーモニックマイナー", "Harmonic Minor", (0, 2, 3, 5, 7, 8, 11), "minor", 0.0,
          "ナチュラルマイナーの 7度を上げたもの。♭6と7の間が 1 音半あき、緊張感があります。",
          "V（ドミナント）のコードの上で使うのが定番。♭6→7→1 の動きがクラシカルです。"),
    Scale("phryg", "フリジアン", "Phrygian", (0, 1, 3, 5, 7, 8, 10), "minor", -0.01,
          "ルートのすぐ上に♭2がある、エキゾチックで重い響き。",
          "低音弦のリフで♭2→1 を繰り返すとメタルやフラメンコの雰囲気になります。"),
    Scale("lydian", "リディアン", "Lydian", (0, 2, 4, 6, 7, 9, 11), "major", -0.01,
          "メジャーの 4度を半音上げた（♯4）浮遊感のある響き。",
          "♯4 をロングトーンにすると映画音楽のような広がりが出ます。"),
]
SCALE_BY_ID = {s.id: s for s in SCALES}

MODE_NAMES = ["アイオニアン", "ドリアン", "フリジアン", "リディアン", "ミクソリディアン", "エオリアン", "ロクリアン"]
MODE_IDS = ["major", "dorian", "phryg", "lydian", "mixo", "minor", None]

# コードの型: 記号, 構成音（ルートからの半音）, 照合用の重み
CHORD_TYPES: list[tuple[str, tuple[int, ...], tuple[float, ...]]] = [
    ("", (0, 4, 7), (1.0, 1.0, 0.8)),
    ("m", (0, 3, 7), (1.0, 1.0, 0.8)),
    ("7", (0, 4, 7, 10), (1.0, 1.0, 0.7, 0.8)),
    ("maj7", (0, 4, 7, 11), (1.0, 1.0, 0.7, 0.8)),
    ("m7", (0, 3, 7, 10), (1.0, 1.0, 0.7, 0.8)),
    ("m7b5", (0, 3, 6, 10), (1.0, 1.0, 0.9, 0.8)),
    ("sus4", (0, 5, 7), (1.0, 1.0, 0.8)),
    ("5", (0, 7), (1.0, 0.9)),
]
CHORD_PRIOR = {"": 0.03, "m": 0.03, "5": -0.02, "sus4": -0.03}

ROMAN = {0: "I", 1: "♭II", 2: "II", 3: "♭III", 4: "III", 5: "IV", 6: "♭V", 7: "V",
         8: "♭VI", 9: "VI", 10: "♭VII", 11: "VII"}
DEGREE = {0: "1", 1: "♭2", 2: "2", 3: "♭3", 4: "3", 5: "4", 6: "♭5", 7: "5",
          8: "♭6", 9: "6", 10: "♭7", 11: "7"}


# ---------------------------------------------------------------- 基本


def note_name(pc: int, flats: bool = False) -> str:
    return (FLAT if flats else SHARP)[pc % 12]


def uses_flats(root: int, mode: str) -> bool:
    """そのキーの調号がフラット系かどうか（マイナーは平行調のメジャーで判断）。"""
    major_root = root if mode == "major" else (root + 3) % 12
    return major_root in FLAT_MAJOR_ROOTS


def degree_name(interval: int, intervals: Iterable[int] = ()) -> str:
    iv = interval % 12
    ivs = set(intervals)
    if iv == 6 and 5 not in ivs and 6 in ivs:
        return "♯4"
    return DEGREE[iv]


def _weight(n: NoteLike) -> float:
    dur = min(max(n.end - n.start, 0.05), 2.0)
    return dur * (0.5 + 0.5 * max(0.0, min(1.0, n.velocity)))


def pitch_class_profile(notes: list[NoteLike], bass_weight: float = 0.5) -> list[float]:
    """12 音それぞれの重み。長く強い音ほど重く、同時に鳴る音のうち最低音を少し重くする。"""
    prof = [0.0] * 12
    for n in notes:
        prof[n.pitch % 12] += _weight(n)
    # 最低音（ベース）はキーの手がかりになりやすい
    for group in _onset_groups(notes):
        low = min(group, key=lambda n: n.pitch)
        prof[low.pitch % 12] += bass_weight * _weight(low)
    return prof


def _onset_groups(notes: list[NoteLike], tol: float = 0.05) -> list[list[NoteLike]]:
    groups: list[list[NoteLike]] = []
    for n in sorted(notes, key=lambda n: n.start):
        if groups and n.start - groups[-1][0].start <= tol:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def _corr(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


def _rotate(profile: list[float], root: int) -> list[float]:
    """root を主音とするプロファイルを、C から並べた 12 音に直す。"""
    return [profile[(p - root) % 12] for p in range(12)]


# ---------------------------------------------------------------- キー


@dataclass
class Key:
    root: int
    mode: str  # "major" / "minor"
    score: float

    @property
    def flats(self) -> bool:
        return uses_flats(self.root, self.mode)

    @property
    def intervals(self) -> tuple[int, ...]:
        return MAJOR_IV if self.mode == "major" else MINOR_IV

    @property
    def pcs(self) -> list[int]:
        return [(self.root + i) % 12 for i in self.intervals]

    def name(self, lang: str = "ja") -> str:
        n = note_name(self.root, self.flats)
        if lang == "ja":
            return f"{n} {'メジャー' if self.mode == 'major' else 'マイナー'}"
        return f"{n} {self.mode}"


def estimate_key(profile: list[float], first: int | None = None, last: int | None = None) -> list[Key]:
    """24 のキーを、プロファイルとの相関が高い順に返す。

    first / last は曲の最初と最後に鳴るベース音の音名。曲は主音で終わることが多いので、
    平行調（C メジャーと A マイナーなど）の見分けに少しだけ使う。
    """
    keys = []
    for r in range(12):
        bonus = (0.02 if first == r else 0.0) + (0.04 if last == r else 0.0)
        keys.append(Key(r, "major", _corr(profile, _rotate(KS_MAJOR, r)) + bonus))
        keys.append(Key(r, "minor", _corr(profile, _rotate(KS_MINOR, r)) + bonus))
    keys.sort(key=lambda k: k.score, reverse=True)
    return keys


def key_confidence(keys: list[Key], distinct: int) -> str:
    if distinct < 4:
        return "low"
    gap = keys[0].score - keys[1].score
    # 平行調どうしは使う音が同じなので差が小さくなりやすい。3 位との差も見る
    gap3 = keys[0].score - keys[2].score
    if gap > 0.08 or (gap > 0.03 and gap3 > 0.12):
        return "high"
    if gap > 0.02 or gap3 > 0.08:
        return "mid"
    return "low"


# ---------------------------------------------------------------- スケール


@dataclass
class ScaleCandidate:
    root: int
    scale: Scale
    score: float
    coverage: float
    unused: list[int]
    outside: list[int]

    @property
    def pcs(self) -> list[int]:
        return [(self.root + i) % 12 for i in self.scale.intervals]


def rank_scales(profile: list[float], key: Key | None = None) -> list[ScaleCandidate]:
    total = sum(profile)
    if total <= 0:
        return []
    peak = max(profile)
    present = [p for p in range(12) if profile[p] > 0.03 * total]
    cands = []
    for r in range(12):
        for sc in SCALES:
            pcs = {(r + i) % 12 for i in sc.intervals}
            coverage = sum(profile[p] for p in pcs) / total
            unused = sorted(p for p in pcs if profile[p] <= 0.02 * total)
            outside = sorted(p for p in present if p not in pcs)
            ks = _corr(profile, _rotate(KS_MAJOR if sc.mode == "major" else KS_MINOR, r))
            score = (
                0.45 * coverage
                + 0.22 * (ks + 1) / 2
                + 0.10 * profile[r] / peak
                - 0.18 * len(unused) / len(pcs)
                + sc.prior
            )
            if key and key.root == r and key.mode == sc.mode:
                score += 0.04
            cands.append(ScaleCandidate(r, sc, score, coverage, unused, outside))
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands


# ---------------------------------------------------------------- コード


@dataclass
class ChordSegment:
    start: float
    end: float
    root: int | None  # None は「コードなし」
    quality: str = ""
    score: float = 0.0
    pcs: list[int] = field(default_factory=list)


def _window_chroma(notes: list[NoteLike], t0: float, t1: float) -> tuple[list[float], int | None]:
    chroma = [0.0] * 12
    low = None
    for n in notes:
        ov = min(n.end, t1) - max(n.start, t0)
        if ov <= 0:
            continue
        w = ov * (0.5 + 0.5 * n.velocity)
        chroma[n.pitch % 12] += w
        if low is None or n.pitch < low.pitch:
            low = n
    if low is not None:
        chroma[low.pitch % 12] += 0.3 * sum(chroma) / max(1, sum(1 for c in chroma if c > 0))
    return chroma, (low.pitch % 12 if low is not None else None)


def _cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def _chord_states() -> list[tuple[int, str, list[float], list[int]]]:
    states = []
    for r in range(12):
        for q, ivs, ws in CHORD_TYPES:
            t = [0.0] * 12
            for iv, w in zip(ivs, ws):
                t[(r + iv) % 12] = w
            states.append((r, q, t, [(r + iv) % 12 for iv in ivs]))
    return states


_STATES = _chord_states()


def estimate_chords(
    notes: list[NoteLike],
    key: Key | None = None,
    window: float = 0.5,
    switch_penalty: float = 0.18,
) -> list[ChordSegment]:
    """時間窓ごとにコードを当て、ビタビで「同じコードが続きやすい」ようにならす。

    単音のメロディだけの音源では和音の情報が少ないので、結果は目安。
    """
    if not notes:
        return []
    t_end = max(n.end for n in notes)
    t_start = min(n.start for n in notes)
    n_win = max(1, math.ceil((t_end - t_start) / window))
    key_pcs = set(key.pcs) if key else set()
    no_chord = len(_STATES)

    emissions: list[list[float]] = []
    for i in range(n_win):
        t0 = t_start + i * window
        chroma, bass = _window_chroma(notes, t0, t0 + window)
        row = []
        if sum(chroma) <= 1e-6:
            row = [0.0] * len(_STATES) + [1.0]
        else:
            for r, q, tmpl, pcs in _STATES:
                s = _cosine(chroma, tmpl) + CHORD_PRIOR.get(q, 0.0)
                if bass == r:
                    s += 0.08
                if key_pcs and all(p in key_pcs for p in pcs):
                    s += 0.05
                row.append(s)
            row.append(0.35)  # 何にも合わないときはコードなし
        emissions.append(row)

    # ビタビ（遷移: 同じ状態なら 0、変わるなら -switch_penalty）
    n_states = len(_STATES) + 1
    score = emissions[0][:]
    back: list[list[int]] = []
    for row in emissions[1:]:
        best_prev = max(range(n_states), key=lambda s: score[s])
        bp_score = score[best_prev] - switch_penalty
        new, ptr = [], []
        for s in range(n_states):
            if score[s] >= bp_score:
                new.append(score[s] + row[s]); ptr.append(s)
            else:
                new.append(bp_score + row[s]); ptr.append(best_prev)
        score = new
        back.append(ptr)
    path = [max(range(n_states), key=lambda s: score[s])]
    for ptr in reversed(back):
        path.append(ptr[path[-1]])
    path.reverse()

    segments: list[ChordSegment] = []
    for i, s in enumerate(path):
        t0 = t_start + i * window
        t1 = min(t_end, t0 + window)
        if segments and segments[-1]._state == s:  # type: ignore[attr-defined]
            segments[-1].end = t1
            segments[-1].score += emissions[i][s]
            segments[-1]._n += 1  # type: ignore[attr-defined]
            continue
        if s == no_chord:
            seg = ChordSegment(t0, t1, None)
        else:
            r, q, _, pcs = _STATES[s]
            seg = ChordSegment(t0, t1, r, q, 0.0, pcs)
        seg.score = emissions[i][s]
        seg._state = s  # type: ignore[attr-defined]
        seg._n = 1  # type: ignore[attr-defined]
        segments.append(seg)
    for seg in segments:
        seg.score /= seg._n  # type: ignore[attr-defined]
    return segments


def chord_name(root: int, quality: str, flats: bool = False) -> str:
    return note_name(root, flats) + quality.replace("b", "♭")


def roman(root: int, quality: str, key: Key) -> str:
    iv = (root - key.root) % 12
    rn = ROMAN[iv]
    minorish = quality.startswith("m") and not quality.startswith("maj")
    if minorish:
        rn = rn.replace("VII", "vii").replace("VI", "vi").replace("IV", "iv").replace("V", "v")
        rn = rn.replace("III", "iii").replace("II", "ii").replace("I", "i")
    suffix = {"m": "", "": "", "m7": "7", "7": "7", "maj7": "maj7", "m7b5": "ø7", "sus4": "sus4", "5": "5"}
    return rn + suffix.get(quality, quality)


# ---------------------------------------------------------------- 提案


def diatonic_chords(key: Key) -> list[dict]:
    """キーのダイアトニックコード（3 和音と 4 和音、機能）。"""
    ivs = key.intervals
    pcs = key.pcs
    out = []
    for i in range(7):
        r, t, f, s = (pcs[(i + k) % 7] for k in (0, 2, 4, 6))
        third, fifth, sev = (t - r) % 12, (f - r) % 12, (s - r) % 12
        q = {(4, 7): "", (3, 7): "m", (3, 6): "dim", (4, 8): "aug"}.get((third, fifth), "")
        q7 = {("", 11): "maj7", ("", 10): "7", ("m", 10): "m7", ("m", 11): "mMaj7",
              ("dim", 10): "m7b5", ("dim", 9): "dim7"}.get((q, sev), q)
        if key.mode == "major":
            func = {0: "トニック", 5: "トニック", 2: "トニック", 3: "サブドミナント", 1: "サブドミナント",
                    4: "ドミナント", 6: "ドミナント"}[i]
        else:
            func = {0: "トニック", 2: "トニック", 3: "サブドミナント", 5: "サブドミナント",
                    1: "サブドミナント", 4: "ドミナント", 6: "ドミナント"}[i]
        out.append({
            "root": r,
            "quality": q,
            "name": chord_name(r, q, key.flats),
            "name7": chord_name(r, q7, key.flats),
            "roman": roman(r, "m7b5" if q == "dim" else q, key).replace("ø7", "°"),
            "function": func,
            "pcs": [r, t, f],
            "pcs7": [r, t, f, s],
            "degree": ivs[i],
        })
    return out


def chord_scale(root: int, quality: str, key: Key) -> dict:
    """そのコードの上でソロを弾くときに使えるスケール。"""
    major_parent = key.root if key.mode == "major" else (key.root + 3) % 12
    parent_pcs = [(major_parent + i) % 12 for i in MAJOR_IV]
    tones = [(root + iv) % 12 for iv in dict((q, ivs) for q, ivs, _ in CHORD_TYPES)[quality]]
    diatonic = all(p in parent_pcs for p in tones)
    if diatonic and root in parent_pcs:
        idx = parent_pcs.index(root)
        sid = MODE_IDS[idx]
        name = MODE_NAMES[idx]
        why = f"キーの音のまま、{note_name(root, key.flats)} から始めた並び（{name}）です。"
        if sid is None:
            return {"root": root, "scale": "minor", "label": f"{note_name(root, key.flats)} ロクリアン",
                    "why": why + "表示はキーのスケールで代用しています。", "diatonic": True, "use_key": True}
        return {"root": root, "scale": sid, "label": f"{note_name(root, key.flats)} {name}",
                "why": why, "diatonic": True, "use_key": False}
    # キーの外のコード
    if key.mode == "minor" and (root - key.root) % 12 == 7 and quality in ("", "7"):
        return {"root": key.root, "scale": "harm", "label": f"{note_name(key.root, key.flats)} ハーモニックマイナー",
                "why": "マイナーキーの V（メジャー）は、キーのハーモニックマイナーで弾くと 7 度が合います。",
                "diatonic": False, "use_key": False}
    if quality == "7":
        sid, why = "mixo", "キーの外のセブンスコード。コードのルートからのミクソリディアンで合わせます。"
    elif quality in ("m", "m7"):
        sid, why = "dorian", "キーの外のマイナーコード。ドリアンかマイナーペンタで合わせます。"
    elif quality == "m7b5":
        sid, why = "minpent", "キーの外の m7♭5。コードトーンを中心に弾くのが安全です。"
    else:
        sid, why = "majpent", "キーの外のメジャーコード。コードのルートからのメジャーペンタが安全です。"
    sc = SCALE_BY_ID[sid]
    return {"root": root, "scale": sid, "label": f"{note_name(root, key.flats)} {sc.ja}", "why": why,
            "diatonic": False, "use_key": False}


def solo_position(root: int) -> int:
    """6 弦でそのルートを押さえるいちばん低いフレット（0 なら 12 も候補）。"""
    return (root - 4) % 12


def solo_suggestions(key: Key, scales: list[ScaleCandidate], profile: list[float]) -> list[dict]:
    """ソロで使えるスケールを、なぜ合うかと弾き方のコツ付きで返す。"""
    total = sum(profile) or 1.0
    flats = key.flats
    out: list[dict] = []
    seen: set[tuple[int, str]] = set()

    def add(root: int, sid: str, why: str) -> None:
        if (root, sid) in seen:
            return
        seen.add((root, sid))
        sc = SCALE_BY_ID[sid]
        pcs = {(root + i) % 12 for i in sc.intervals}
        fit = sum(profile[p] for p in pcs) / total
        pos = solo_position(root)
        out.append({
            "root": root, "scale": sid, "label": f"{note_name(root, flats)} {sc.ja}",
            "why": why, "tip": sc.solo_tip, "fit": round(fit, 3),
            "position": pos if pos else 12,
        })

    k = key.root
    has = lambda iv: profile[(k + iv) % 12] > 0.03 * total  # noqa: E731
    if key.mode == "minor":
        add(k, "minpent", "マイナーキーのソロの定番。曲の音のほとんどに合い、外れにくい 5 音です。")
        if has(9) and not has(8):
            add(k, "dorian", "曲の中に 6 度（ナチュラルマイナーより半音高い音）が出てくるので、ドリアンがよく合います。")
        else:
            add(k, "minor", "キーの音をすべて使う形。ペンタに 2 度と♭6 度を足すと表情が増えます。")
        if has(11):
            add(k, "harm", "曲に 7 度（導音）が出てくるので、V のコードの上ではハーモニックマイナーが合います。")
        add(k, "blues", "♭5 を経過音として足すとブルージーになります。ロックやブルース寄りの曲に。")
        add((k + 3) % 12, "majpent", "平行調のメジャーペンタ。同じ音で、明るいフレーズの組み立てになります。")
    else:
        add(k, "majpent", "メジャーキーのソロの定番。明るく外れにくい 5 音です。")
        if has(10) and not has(11):
            add(k, "mixo", "曲の中に♭7 度が出てくるので、ミクソリディアンがよく合います。")
        else:
            add(k, "major", "キーの音をすべて使う形。4 度と 7 度は経過音として使うと安定します。")
        add((k + 9) % 12, "minpent", "平行調のマイナーペンタ（同じ音の並び）。ロックっぽい手癖のフレーズがそのまま使えます。")
        add(k, "minpent", "あえて同じルートのマイナーペンタを混ぜると、ブルースロックの雰囲気になります（♭3 は 3 へのチョーキングで）。")
    # 推定上位のスケールで、まだ挙がっていないもの
    for c in scales[:3]:
        if c.coverage > 0.9:
            add(c.root, c.scale.id, "使われている音の分布からも有力な候補です。")
    return out[:6]


def arrangement_ideas(key: Key, segments: list[ChordSegment]) -> list[dict]:
    """コード進行をアレンジするときの候補（代理コード・セブンス化・セカンダリードミナント）。"""
    flats = key.flats
    seen = []
    for s in segments:
        if s.root is None or (s.end - s.start) < 0.4:
            continue
        if (s.root, s.quality) not in seen:
            seen.append((s.root, s.quality))
    ideas = []
    for root, q in seen[:6]:
        name = chord_name(root, q, flats)
        alts = []
        iv = (root - key.root) % 12
        base_q = "m" if q in ("m", "m7") else ("" if q in ("", "7", "maj7", "5", "sus4") else q)
        if base_q == "":
            rel = (root + 9) % 12
            alts.append({"name": chord_name(rel, "m7", flats), "why": "平行調のコード（共通音が 2 つ）で、柔らかく置き換えられます。"})
            if iv == 7:
                alts.append({"name": chord_name(root, "7", flats), "why": "ドミナントをセブンスにすると、トニックに戻る力が強くなります。"})
                alts.append({"name": chord_name((root + 6) % 12, "7", True),
                             "why": "裏コード（三全音代理）。ベースが半音で下がるジャジーな響きになります。"})
                alts.append({"name": chord_name(root, "sus4", flats) + " → " + name,
                             "why": "sus4 を挟んでから解決させると、ためが生まれます。"})
            elif iv in (0, 5):
                alts.append({"name": chord_name(root, "maj7", flats), "why": "メジャーセブンスにすると、おしゃれで浮遊感のある響きになります。"})
                alts.append({"name": chord_name(root, "add9", flats), "why": "9 度を足すと、開放弦が鳴るような広がりが出ます。"})
            if iv == 5 and key.mode == "major":
                alts.append({"name": chord_name(root, "m", flats),
                             "why": "サブドミナントマイナー（IV を m に）。切ない響きでサビの終わりなどに定番です。"})
        elif base_q == "m":
            rel = (root + 3) % 12
            alts.append({"name": chord_name(rel, "maj7", flats), "why": "平行調のメジャー側に置き換えると明るくなります。"})
            alts.append({"name": chord_name(root, "m7", flats), "why": "7 度を足すと、より滑らかにつながります。"})
            if key.mode == "minor" and iv == 7:
                alts.append({"name": chord_name(root, "7", flats),
                             "why": "マイナーキーの v を V7 にすると、トニックへ強く戻ります（ハーモニックマイナー）。"})
        if iv != 0:
            alts.append({"name": chord_name((root + 7) % 12, "7", flats) + " → " + name,
                         "why": f"{name} の前にそのドミナント（セカンダリードミナント）を挟むと、進行に勢いが出ます。"})
        ideas.append({"chord": name, "roman": roman(root, q, key), "alternatives": alts[:4]})
    return ideas


# ---------------------------------------------------------------- まとめ


def analyze_theory(notes: list[NoteLike], chord_window: float = 0.5) -> dict | None:
    """画面に渡す形のキー・スケール・コード・提案。ノートが少なすぎるときは None。"""
    if not notes:
        return None
    profile = pitch_class_profile(notes)
    total = sum(profile)
    distinct = sum(1 for p in profile if p > 0.02 * total)
    if distinct < 2:
        return None
    groups = _onset_groups(notes)
    first = min(groups[0], key=lambda n: n.pitch).pitch % 12
    last = min(groups[-1], key=lambda n: n.pitch).pitch % 12
    keys = estimate_key(profile, first, last)
    key = keys[0]
    flats = key.flats
    scales = rank_scales(profile, key)
    segments = estimate_chords(notes, key, window=chord_window)

    # 平行調の候補（使う音が同じ）が 2 位なら、その旨を伝える
    runner = keys[1]
    relative = (
        runner.mode != key.mode and set(runner.pcs) == set(key.pcs)
    )

    chord_list = []
    for s in segments:
        item = {"start": round(s.start, 3), "end": round(s.end, 3)}
        if s.root is None:
            item.update({"name": None})
        else:
            item.update({
                "root": s.root, "quality": s.quality, "pcs": s.pcs,
                "name": chord_name(s.root, s.quality, flats),
                "roman": roman(s.root, s.quality, key),
                "diatonic": all(p in key.pcs for p in s.pcs),
                "confidence": round(min(1.0, max(0.0, s.score)), 2),
                "scale": chord_scale(s.root, s.quality, key),
            })
        chord_list.append(item)

    return {
        "profile": [round(p / total, 4) for p in profile],
        "key": {
            "root": key.root, "mode": key.mode, "name": key.name(), "name_en": key.name("en"),
            "flats": flats, "score": round(key.score, 3),
            "confidence": key_confidence(keys, distinct),
            "relative_ambiguous": relative,
        },
        "key_candidates": [
            {"root": k.root, "mode": k.mode, "name": k.name(), "score": round(k.score, 3), "flats": k.flats}
            for k in keys[:5]
        ],
        "scale_candidates": [
            {
                "root": c.root, "scale": c.scale.id, "label": f"{note_name(c.root, flats)} {c.scale.ja}",
                "score": round(c.score, 3), "coverage": round(c.coverage, 3),
                "unused": c.unused, "outside": c.outside,
            }
            for c in scales[:8]
        ],
        "chords": chord_list,
        "diatonic": diatonic_chords(key),
        "solo": solo_suggestions(key, scales, profile),
        "arrangement": arrangement_ideas(key, segments),
        "scales": [
            {"id": s.id, "ja": s.ja, "en": s.en, "intervals": list(s.intervals), "mode": s.mode,
             "desc": s.desc, "tip": s.solo_tip}
            for s in SCALES
        ],
    }
