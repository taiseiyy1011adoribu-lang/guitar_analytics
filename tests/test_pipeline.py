from guitar_analytics.simple_fingering import assign_frets, fold_into_range
from guitar_analytics.tab import render_tab
from guitar_analytics.transcribe import Note, drop_harmonics, group_events


def test_single_notes_use_lowest_fret():
    # E2 は 6 弦開放、E4 は 1 弦開放、B3 は 2 弦開放
    assert assign_frets([[40], [64], [59]]) == [[(6, 0)], [(1, 0)], [(2, 0)]]


def test_chord_uses_distinct_strings_and_keeps_order():
    # 開放の E メジャー（入力順は低い音から）
    chord = [40, 47, 52, 56, 59, 64]
    (result,) = assign_frets([chord])
    assert result == [(6, 0), (5, 2), (4, 2), (3, 1), (2, 0), (1, 0)]
    assert len({s for s, _ in result}) == 6


def test_unplayable_note_becomes_none():
    # 同じ音が 7 つは 6 本の弦では弾けない
    (result,) = assign_frets([[52] * 7])
    assert result.count(None) >= 1


def test_out_of_range_is_folded_by_octave():
    assert fold_into_range(30) == 42
    assert fold_into_range(100) == 76


def test_render_tab():
    text = render_tab([[(6, 0)], [(5, 12)], [None]])
    assert text.splitlines() == [
        "e|------|",
        "B|------|",
        "G|------|",
        "D|------|",
        "A|---12-|",
        "E|-0----|",
    ]


def test_render_tab_wraps():
    text = render_tab([[(1, 0)]] * 40, width=30)
    lines = text.splitlines()
    assert all(len(line) <= 30 for line in lines)
    assert "" in lines  # 段の区切り


def test_group_events_merges_close_onsets():
    notes = [Note(0.0, 1, 40, 0.8), Note(0.03, 1, 47, 0.8), Note(0.5, 1, 52, 0.8)]
    assert group_events(notes, tolerance=0.05) == [(0.0, [40, 47]), (0.5, [52])]


def test_drop_harmonics_removes_weak_octave():
    notes = [Note(0.0, 0.5, 52, 0.8), Note(0.0, 0.4, 64, 0.4), Note(1.0, 1.5, 64, 0.8)]
    assert [n.pitch for n in drop_harmonics(notes)] == [52, 64]
