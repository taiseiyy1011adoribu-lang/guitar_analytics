"""弦・フレット割り当て（運指推定）モジュール。

ノート列（各イベント＝同時に鳴る MIDI ノートの集合）に対して、
各ノートを「どの弦の何フレットで弾くか」を動的計画法（ビタビ）で決める。

考え方
------
* 状態 = 1 イベント分の押さえ方（各ノート → (弦, フレット)、同時発音は必ず別弦）と
  手のポジション（人差し指のフレット）の組
* 状態コスト = その押さえ方自体の弾きにくさ（ストレッチ、ハイポジション、開放弦ボーナスなど）
* 遷移コスト = 手のポジション移動量、大きなシフト、単音での弦の飛び越しなど
* ビタビで「状態コスト + 遷移コスト」の合計が最小になる経路を選ぶ

弦番号は 1 = 1弦（高音E）〜 6 = 6弦（低音E）。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Optional, Sequence

# 標準チューニング（6弦→1弦ではなく、弦番号→開放弦の MIDI ノート）
STANDARD_TUNING: dict[int, int] = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}

Fingering = tuple[tuple[int, int, int], ...]  # ((pitch, string, fret), ...) pitch 昇順


@dataclass(frozen=True)
class CostWeights:
    """コストの重み。値を変えると好みの弾き方に調整できる。"""

    # --- 状態コスト（1つの押さえ方の弾きにくさ） ---
    span: float = 1.0            # 押さえる指の間のフレット幅 1 あたり
    span_limit: int = 4          # これを超えるストレッチは急に苦しくなる
    over_span: float = 4.0       # span_limit を 1 超えるごとの追加コスト
    high_fret: float = 0.08      # 手のポジション 1 フレットあたり（高いポジションをやや避ける）
    open_string: float = -0.3    # 開放弦 1 本あたり（負＝ボーナス）
    string_gap: float = 0.5      # 和音で間に弾かない弦を挟むごと（ミュートが必要）

    # --- 遷移コスト（押さえ方 → 次の押さえ方） ---
    hand_move: float = 1.0       # 手のポジション移動 1 フレットあたり
    big_jump: int = 5            # これを超える移動はシフトとして追加コスト
    big_jump_penalty: float = 3.0
    string_move: float = 0.3     # 単音どうしで弦をまたぐ 1 本あたり


@dataclass(frozen=True)
class FretConfig:
    tuning: tuple[tuple[int, int], ...] = tuple(sorted(STANDARD_TUNING.items()))
    max_fret: int = 20
    hard_span_limit: int = 7     # これを超える押さえ方は候補から除外


@dataclass(frozen=True)
class NotePosition:
    pitch: int
    string: int
    fret: int


# ---------------------------------------------------------------------------
# 候補の列挙
# ---------------------------------------------------------------------------

def note_positions(pitch: int, config: FretConfig = FretConfig()) -> list[tuple[int, int]]:
    """1 つのノートを弾ける (弦, フレット) の一覧。"""
    out = []
    for string, open_pitch in config.tuning:
        fret = pitch - open_pitch
        if 0 <= fret <= config.max_fret:
            out.append((string, fret))
    return out


def fold_into_range(pitch: int, config: FretConfig = FretConfig()) -> int:
    """音域外のノートをオクターブ単位で弾ける音域に移す。"""
    lo = min(op for _, op in config.tuning)
    hi = max(op for _, op in config.tuning) + config.max_fret
    while pitch < lo:
        pitch += 12
    while pitch > hi:
        pitch -= 12
    return pitch


def _fretted(f: Fingering) -> list[int]:
    return [fret for _, _, fret in f if fret > 0]


def _span(f: Fingering) -> int:
    frets = _fretted(f)
    return max(frets) - min(frets) if frets else 0


def fingers_needed(f: Fingering) -> int:
    """必要な指の本数。最低フレットのノートは人差し指のセーハ 1 本でまとめて押さえられるとみなす。"""
    frets = _fretted(f)
    if not frets:
        return 0
    lo = min(frets)
    return 1 + sum(1 for fr in frets if fr != lo)


def candidate_fingerings(pitches: Sequence[int], config: FretConfig = FretConfig()) -> list[Fingering]:
    """同時に鳴るノート集合の押さえ方をすべて列挙する（同じ弦は使わない）。

    すべてを同時に弾ける押さえ方が無い場合は、低いノートから順に
    省いて弾ける形を探す（7 音以上・音域外などへの保険）。
    """
    pitches = sorted(set(fold_into_range(p, config) for p in pitches))
    while pitches:
        options = [note_positions(p, config) for p in pitches]
        result: list[Fingering] = []
        for combo in product(*options):
            strings = [s for s, _ in combo]
            if len(set(strings)) != len(strings):
                continue
            f = tuple((p, s, fr) for p, (s, fr) in zip(pitches, combo))
            if _span(f) <= config.hard_span_limit and fingers_needed(f) <= 4:
                result.append(f)
        if result:
            return result
        pitches = pitches[1:]  # 一番低いノートを省いてやり直す
    return [()]  # 何も弾けない（休符扱い）


# ---------------------------------------------------------------------------
# コスト
# ---------------------------------------------------------------------------
#
# 状態は (押さえ方, 手のポジション p) の組。p は人差し指を置くフレットで、
# 押さえるフレットはすべて p〜p+3（4本の指が届く範囲）に入る必要がある。
# 開放弦だけの押さえ方は手がどこにあってもよいので、すべての p を候補にする。
# こうすると「同じポジションの中で弦を変える」ことに移動コストがかからず、
# ポジション移動だけが手の移動として数えられる。

FINGER_REACH = 3  # 人差し指から小指までのフレット幅


def hand_positions(f: Fingering, config: FretConfig = FretConfig()) -> list[int]:
    """押さえ方 f を弾けるポジション p の候補。"""
    frets = _fretted(f)
    top = config.max_fret - FINGER_REACH
    if not frets:
        return list(range(1, top + 1))
    lo, hi = min(frets), max(frets)
    if hi - lo > FINGER_REACH:  # ストレッチ：人差し指は最低フレット
        return [lo]
    return list(range(max(1, hi - FINGER_REACH), lo + 1))


def state_cost(f: Fingering, p: int, w: CostWeights = CostWeights()) -> float:
    """押さえ方 f をポジション p で弾くこと自体のコスト。"""
    if not f:
        return 0.0
    cost = 0.0
    span = _span(f)
    cost += w.span * span
    if span > w.span_limit:
        cost += w.over_span * (span - w.span_limit)
    cost += w.high_fret * p
    cost += w.open_string * sum(1 for _, _, fr in f if fr == 0)
    if len(f) > 1:
        strings = sorted(s for _, s, _ in f)
        gaps = (strings[-1] - strings[0] + 1) - len(strings)
        cost += w.string_gap * gaps
    return cost


def transition_cost(prev: Fingering, prev_p: int, cur: Fingering, cur_p: int,
                    w: CostWeights = CostWeights()) -> float:
    """(prev, prev_p) → (cur, cur_p) の遷移コスト。"""
    d = abs(cur_p - prev_p)
    cost = w.hand_move * d
    if d > w.big_jump:
        cost += w.big_jump_penalty
    if len(prev) == 1 and len(cur) == 1:
        cost += w.string_move * abs(prev[0][1] - cur[0][1])
    return cost


# ---------------------------------------------------------------------------
# ビタビ
# ---------------------------------------------------------------------------

def _viterbi(states_per_step: list[list[tuple[Fingering, int]]],
             w: CostWeights) -> tuple[float, list[tuple[Fingering, int]]]:
    """各時刻の状態候補から合計コスト最小の経路を求める。"""
    first = states_per_step[0]
    dp = [state_cost(f, p, w) for f, p in first]
    back: list[list[int]] = [[-1] * len(first)]
    for t in range(1, len(states_per_step)):
        prev_states, cur_states = states_per_step[t - 1], states_per_step[t]
        new_dp, bp = [], []
        for f, p in cur_states:
            best, best_i = float("inf"), -1
            for i, (pf, pp) in enumerate(prev_states):
                c = dp[i] + transition_cost(pf, pp, f, p, w)
                if c < best:
                    best, best_i = c, i
            new_dp.append(best + state_cost(f, p, w))
            bp.append(best_i)
        dp, _ = new_dp, back.append(bp)
    j = min(range(len(dp)), key=dp.__getitem__)
    best_total = dp[j]
    path = [None] * len(states_per_step)
    for t in range(len(states_per_step) - 1, -1, -1):
        path[t] = states_per_step[t][j]
        j = back[t][j]
    return best_total, path  # type: ignore[return-value]


def _expand(f: Fingering, config: FretConfig) -> list[tuple[Fingering, int]]:
    return [(f, p) for p in hand_positions(f, config)]


def assign_positions(events: Iterable[Sequence[int]],
                     weights: CostWeights = CostWeights(),
                     config: FretConfig = FretConfig()) -> list[list[NotePosition]]:
    """イベント列（各要素は同時に鳴る MIDI ノートのリスト）に最適な弦・フレットを割り当てる。

    戻り値はイベントごとの NotePosition のリスト（ピッチ昇順）。
    """
    events = [list(e) for e in events]
    if not events:
        return []
    states = [[s for f in candidate_fingerings(e, config) for s in _expand(f, config)]
              for e in events]
    _, path = _viterbi(states, weights)
    return [[NotePosition(p, s, fr) for p, s, fr in f] for f, _ in path]


def assign_frets(events: Iterable[Sequence[int]],
                 weights: CostWeights = CostWeights(),
                 config: FretConfig = FretConfig()) -> list[list[Optional[tuple[int, int]]]]:
    """パイプライン用の入口。入力と同じ形で (string, fret) を返す。

    各イベント内の順番は入力のノート順のまま。音域外のノートはオクターブを
    移して割り当てる。どうしても弾けず省いたノート（7 音以上の和音など）は None。
    同じピッチが重複していれば同じ位置を返す。
    """
    events = [list(e) for e in events]
    result = assign_positions(events, weights, config)
    out = []
    for ev, placed in zip(events, result):
        by_pitch = {n.pitch: (n.string, n.fret) for n in placed}
        out.append([by_pitch.get(fold_into_range(p, config)) for p in ev])
    return out


def _best_hand_path(assignment: Sequence[Sequence[NotePosition]],
                    weights: CostWeights, config: FretConfig) -> tuple[float, list[int]]:
    """押さえ方を固定したとき、手のポジションを最適に選んだ場合のコストと経路。"""
    fs = [tuple((n.pitch, n.string, n.fret) for n in ev) for ev in assignment]
    if not fs:
        return 0.0, []
    total, path = _viterbi([_expand(f, config) for f in fs], weights)
    return total, [p for _, p in path]


def total_cost(assignment: Sequence[Sequence[NotePosition]],
               weights: CostWeights = CostWeights(),
               config: FretConfig = FretConfig()) -> float:
    """割り当て結果の合計コスト（比較用。手のポジションは最適に選んだとして計算）。"""
    return _best_hand_path(assignment, weights, config)[0]


def hand_travel(assignment: Sequence[Sequence[NotePosition]],
                weights: CostWeights = CostWeights(),
                config: FretConfig = FretConfig()) -> int:
    """手のポジション移動量の合計（フレット数）。"""
    _, ps = _best_hand_path(assignment, weights, config)
    return sum(abs(b - a) for a, b in zip(ps, ps[1:]))


# ---------------------------------------------------------------------------
# 比較用の単純ルール
# ---------------------------------------------------------------------------

def assign_frets_naive(events: Iterable[Sequence[int]],
                       config: FretConfig = FretConfig()) -> list[list[NotePosition]]:
    """単純ルール：各イベントを前後を見ずに「一番低いフレット」で弾く。

    単音なら最もフレット番号が小さい弦、和音なら最高フレットが最小になる押さえ方。
    """
    out = []
    for e in events:
        cands = candidate_fingerings(e, config)
        best = min(cands, key=lambda f: (max((fr for _, _, fr in f), default=0),
                                         sum(fr for _, _, fr in f)))
        out.append([NotePosition(p, s, fr) for p, s, fr in best])
    return out


# ---------------------------------------------------------------------------
# テキストタブ譜
# ---------------------------------------------------------------------------

def to_ascii_tab(assignment: Sequence[Sequence[NotePosition]],
                 config: FretConfig = FretConfig()) -> str:
    strings = sorted(s for s, _ in config.tuning)  # 1..6
    names = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}
    cols: list[dict[int, str]] = []
    for ev in assignment:
        cols.append({n.string: str(n.fret) for n in ev})
    lines = []
    for s in strings:
        row = []
        for col in cols:
            width = max([len(v) for v in col.values()] + [1])
            row.append(col.get(s, "-").ljust(width, "-"))
        lines.append(f"{names.get(s, str(s))}|-" + "-".join(row) + "-|")
    return "\n".join(lines)
