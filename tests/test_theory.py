from guitar_analytics.theory import (
    analyze_theory,
    chord_scale,
    diatonic_chords,
    estimate_chords,
    estimate_key,
    pitch_class_profile,
    rank_scales,
    Key,
)
from guitar_analytics.transcribe import Note


def _melody(pitches, step=0.5, start=0.0):
    return [Note(start + i * step, start + i * step + step * 0.9, p, 0.8) for i, p in enumerate(pitches)]


def _chord(t, pitches, dur=1.9):
    return [Note(t, t + dur, p, 0.7) for p in pitches]


def test_a_minor_pentatonic_phrase():
    # A マイナーペンタの典型的なフレーズ（A で始まり A で終わる）
    notes = _melody([45, 57, 60, 62, 64, 67, 64, 62, 60, 57, 55, 57, 45])
    prof = pitch_class_profile(notes)
    keys = estimate_key(prof, first=9, last=9)
    assert (keys[0].root, keys[0].mode) == (9, "minor")
    top = rank_scales(prof, keys[0])[0]
    assert top.root == 9 and top.scale.id == "minpent"


def test_c_major_scale():
    notes = _melody([48, 50, 52, 53, 55, 57, 59, 60, 59, 57, 55, 53, 52, 50, 48], step=0.4)
    r = analyze_theory(notes)
    assert r["key"]["name"] == "C メジャー"
    assert r["scale_candidates"][0]["label"] == "C メジャー"


def test_chord_progression_is_detected_and_smoothed():
    # Am - F - C - G を 2 秒ずつ
    prog = [[45, 57, 60, 64], [41, 57, 60, 65], [48, 55, 60, 64], [43, 55, 59, 62]]
    notes = [n for i, c in enumerate(prog) for n in _chord(i * 2.0, c)]
    key = Key(0, "major", 1.0)
    segs = [s for s in estimate_chords(notes, key) if s.root is not None]
    names = [(s.root, s.quality) for s in segs]
    assert names == [(9, "m"), (5, ""), (0, ""), (7, "")]
    assert abs(segs[1].start - 2.0) < 0.51


def test_flat_keys_are_spelled_with_flats():
    # F メジャーのダイアトニックコードは B♭ を含む
    names = [d["name"] for d in diatonic_chords(Key(5, "major", 1.0))]
    assert names == ["F", "Gm", "Am", "Bb", "C", "Dm", "Edim"]


def test_chord_scale_suggestions():
    c_major = Key(0, "major", 1.0)
    assert chord_scale(2, "m", c_major)["scale"] == "dorian"  # ii は D ドリアン
    assert chord_scale(7, "7", c_major)["scale"] == "mixo"  # V7 は G ミクソリディアン
    a_minor = Key(9, "minor", 1.0)
    s = chord_scale(4, "7", a_minor)  # マイナーキーの V7（E7）
    assert s["scale"] == "harm" and s["root"] == 9


def test_analyze_theory_shape_and_suggestions():
    prog = [[45, 57, 60, 64], [41, 57, 60, 65], [48, 55, 60, 64], [43, 55, 59, 62], [45, 57, 60, 64]]
    notes = [n for i, c in enumerate(prog) for n in _chord(i * 2.0, c)]
    notes += _melody([69, 72, 74, 76, 79, 76, 74, 72, 69], start=0.0)
    r = analyze_theory(notes)
    assert r["key"]["root"] == 9 and r["key"]["mode"] == "minor"  # A で始まり A で終わる
    assert r["key"]["relative_ambiguous"]  # 2 位は同じ音の C メジャー
    assert r["solo"][0]["label"] == "A マイナーペンタトニック" and r["solo"][0]["position"] == 5
    assert [c["name"] for c in r["chords"] if c["name"]][:4] == ["Am", "F", "C", "G"]
    assert all(c["diatonic"] for c in r["chords"] if c["name"])
    assert len(r["diatonic"]) == 7 and r["arrangement"]
    assert {s["id"] for s in r["scales"]} >= {"minpent", "dorian", "mixo"}


def test_too_few_notes():
    assert analyze_theory([]) is None
    assert analyze_theory(_melody([60, 72])) is None  # 同じ音名だけ
