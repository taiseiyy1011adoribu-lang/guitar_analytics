from guitar_analytics.fingering import (
    CostWeights, NotePosition, assign_frets, assign_frets_naive, assign_positions,
    candidate_fingerings, fingers_needed, hand_travel, note_positions, to_ascii_tab, total_cost,
)


def test_note_positions_e4():
    # E4 (64) は 1弦開放, 2弦5, 3弦9, 4弦14, 5弦19
    assert set(note_positions(64)) == {(1, 0), (2, 5), (3, 9), (4, 14), (5, 19)}


def test_chord_notes_on_distinct_strings():
    for f in candidate_fingerings([48, 52, 55, 60, 64]):  # C メジャー
        strings = [s for _, s, _ in f]
        assert len(strings) == len(set(strings))


def test_open_c_chord_is_chosen():
    (chord,) = assign_positions([[48, 52, 55, 60, 64]])
    got = {(n.string, n.fret) for n in chord}
    assert got == {(5, 3), (4, 2), (3, 0), (2, 1), (1, 0)}


def test_empty_input():
    assert assign_frets([]) == []


def test_output_shape_and_order_match_input():
    events = [[64], [67, 60], [55]]
    out = assign_frets(events)
    assert [len(e) for e in out] == [1, 2, 1]
    for ev, pos in zip(events, out):
        for pitch, (string, fret) in zip(ev, pos):
            open_pitch = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}[string]
            assert open_pitch + fret == pitch


def test_out_of_range_note_is_octave_shifted():
    (pos,) = assign_frets([[28]])  # E1 は低すぎる → E2 (6弦開放)
    assert pos == [(6, 0)]


def test_too_many_notes_returns_none_for_dropped():
    out = assign_frets([[40, 45, 50, 55, 59, 64, 69]])[0]
    assert out.count(None) >= 1
    assert len(out) == 7


def test_viterbi_stays_in_position_for_high_run():
    # 7〜9フレット付近の A マイナーペンタ風フレーズ。
    # 単純ルールは開放弦〜低フレットへ飛び回るが、ビタビは同じポジションに留まる。
    phrase = [[69], [72], [74], [76], [74], [72], [69], [67], [64]]
    smart = assign_positions(phrase)
    naive = assign_frets_naive(phrase)
    assert total_cost(smart) <= total_cost(naive)
    assert hand_travel(smart) <= hand_travel(naive)


def test_viterbi_is_optimal_vs_bruteforce():
    from itertools import product
    phrase = [[62], [64, 67], [69], [71]]
    w = CostWeights()
    best = min(
        total_cost([[NotePosition(*x) for x in f] for f in combo], w)
        for combo in product(*[candidate_fingerings(e) for e in phrase])
    )
    assert abs(total_cost(assign_positions(phrase, w), w) - best) < 1e-9


def test_ascii_tab_has_six_lines():
    tab = to_ascii_tab(assign_positions([[64], [60]]))
    assert len(tab.splitlines()) == 6


def test_fingers_needed_limits_chord_shapes():
    for f in candidate_fingerings([40, 47, 52, 56, 59, 64]):  # E メジャー 6 音
        assert fingers_needed(f) <= 4


def test_barre_counts_as_one_finger():
    # F のセーハ: 6弦1, 5弦3, 4弦3, 3弦2, 2弦1, 1弦1
    f = ((41, 6, 1), (48, 5, 3), (53, 4, 3), (57, 3, 2), (60, 2, 1), (65, 1, 1))
    assert fingers_needed(f) == 4


def test_smart_beats_naive_on_example_phrases():
    phrase = [[57, 64, 69, 72], [72], [71], [69], [53, 60, 65, 69], [69], [67], [65]]
    smart, naive = assign_positions(phrase), assign_frets_naive(phrase)
    assert total_cost(smart) < total_cost(naive)
