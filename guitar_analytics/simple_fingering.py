"""単純なルールで MIDI ノートを弦とフレットに割り当てる。

インターフェースは assign_frets(events) で、より賢い割り当て
（guitar_analytics.fingering）と差し替えられるようにしてある。
"""
from __future__ import annotations

# 標準チューニング。キーは弦番号（1=高音E 〜 6=低音E）、値は開放弦の MIDI 番号
STANDARD_TUNING = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
MAX_FRET = 20
LOWEST = min(STANDARD_TUNING.values())
HIGHEST = max(STANDARD_TUNING.values()) + MAX_FRET


def fold_into_range(pitch: int) -> int:
    """ギターで出せない音を最寄りのオクターブに移す。"""
    while pitch < LOWEST:
        pitch += 12
    while pitch > HIGHEST:
        pitch -= 12
    return pitch


def candidates(pitch: int) -> list[tuple[int, int]]:
    """その音を出せる (弦, フレット) を全部返す。"""
    return [
        (string, pitch - open_pitch)
        for string, open_pitch in STANDARD_TUNING.items()
        if 0 <= pitch - open_pitch <= MAX_FRET
    ]


def assign_frets(events: list[list[int]]) -> list[list[tuple[int, int] | None]]:
    """各イベント（同時に鳴るノートのリスト）を (弦, フレット) に割り当てる。

    ルール: 高い音から順に、まだ使っていない弦の中で一番低いフレットを選ぶ。
    同時に弾けないノートは None になる。戻り値は入力と同じ形・同じ順番。
    """
    result: list[list[tuple[int, int] | None]] = []
    for pitches in events:
        assigned: list[tuple[int, int] | None] = [None] * len(pitches)
        used: set[int] = set()
        order = sorted(range(len(pitches)), key=lambda i: -pitches[i])
        for i in order:
            options = [c for c in candidates(fold_into_range(pitches[i])) if c[0] not in used]
            if options:
                best = min(options, key=lambda c: (c[1], c[0]))
                assigned[i] = best
                used.add(best[0])
        result.append(assigned)
    return result
