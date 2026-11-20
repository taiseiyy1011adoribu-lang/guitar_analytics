from guitar_analytics.rhythm import (
    Grid,
    TimedEvent,
    duration_symbol,
    group_timed_events,
    make_grid,
    quantize,
)
from guitar_analytics.tab import render_rhythm_tab
from guitar_analytics.transcribe import Note


def test_quantize_quarter_notes_at_120bpm():
    grid = Grid(bpm=120, offset=0.0)  # 16 分音符 = 0.125 秒
    events = [TimedEvent(0.01, 0.45, [52]), TimedEvent(0.51, 0.95, [55]), TimedEvent(1.0, 2.5, [57])]
    q = quantize(events, grid)
    assert [(e.step, e.length) for e in q] == [(0, 4), (4, 4), (8, 12)]


def test_short_note_before_long_gap_keeps_its_own_length():
    grid = Grid(bpm=120, offset=0.0)
    # 8 分音符を鳴らしてから 2 拍休む
    q = quantize([TimedEvent(0.0, 0.25, [52]), TimedEvent(1.5, 2.0, [55])], grid)
    assert (q[0].step, q[0].length) == (0, 2)


def test_events_on_same_step_are_merged():
    grid = Grid(bpm=120, offset=0.0)
    q = quantize([TimedEvent(0.0, 0.5, [40]), TimedEvent(0.06, 0.5, [47])], grid)
    assert len(q) == 1 and q[0].pitches == [40, 47]


def test_make_grid_aligns_to_beat_phase():
    grid = make_grid(120, [0.53, 1.03, 1.53], first_onset=0.01)
    assert abs(grid.offset - 0.03) < 1e-9


def test_group_timed_events_keeps_longest_end():
    notes = [Note(0.0, 0.5, 40, 0.8), Note(0.02, 1.5, 47, 0.8)]
    assert group_timed_events(notes) == [TimedEvent(0.0, 1.5, [40, 47])]


def test_duration_symbol():
    assert duration_symbol(4, 16) == "q"
    assert duration_symbol(6, 16) == "q."
    assert duration_symbol(5, 16) == "q"  # 近い短い方
    assert duration_symbol(16, 4) == "q"  # 小節の残りで切る


def test_render_rhythm_tab_bar_lines_and_symbols():
    text = render_rhythm_tab([[(6, 0)], [(1, 3)]], steps=[0, 8], lengths=[8, 8], steps_per_bar=8)
    lines = text.splitlines()
    assert lines[0].startswith("  h")
    assert lines[1] == "e|----------------|3---------------|"
    assert lines[6] == "E|0---------------|----------------|"
