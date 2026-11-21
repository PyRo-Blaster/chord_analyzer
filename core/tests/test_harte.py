import dataclasses

import pytest

from jca_core.chords.harte import InvalidChordLabelError, parse_chord


@pytest.mark.parametrize(
    ("label", "root", "root_pc", "intervals", "bass_interval"),
    [
        ("C:maj", "C", 0, {0, 4, 7}, 0),
        ("C", "C", 0, {0, 4, 7}, 0),
        ("A#", "A#", 10, {0, 4, 7}, 0),
        ("D:min7", "D", 2, {0, 3, 7, 10}, 0),
        ("C:7(b9)", "C", 0, {0, 1, 4, 7, 10}, 0),
        ("C:9", "C", 0, {0, 2, 4, 7, 10}, 0),
        ("C:13", "C", 0, {0, 2, 4, 5, 7, 9, 10}, 0),
        ("C:maj7(#11)", "C", 0, {0, 4, 6, 7, 11}, 0),
        ("C:sus4", "C", 0, {0, 5, 7}, 0),
        ("C:hdim7", "C", 0, {0, 3, 6, 10}, 0),
        ("C:dim7", "C", 0, {0, 3, 6, 9}, 0),
        ("C:7(*5)", "C", 0, {0, 4, 10}, 0),
        ("C:maj/3", "C", 0, {0, 4, 7}, 4),
        ("D:min7/b7", "D", 2, {0, 3, 7, 10}, 10),
        ("Bb:maj6", "Bb", 10, {0, 4, 7, 9}, 0),
        ("F#:minmaj7", "F#", 6, {0, 3, 7, 11}, 0),
    ],
)
def test_parse_chord(label, root, root_pc, intervals, bass_interval):
    parsed = parse_chord(label)
    assert parsed.label == label
    assert parsed.root == root
    assert parsed.root_pc == root_pc
    assert parsed.intervals == frozenset(intervals)
    assert parsed.bass_interval == bass_interval
    assert not parsed.is_no_chord


@pytest.mark.parametrize("label", ["N", "X"])
def test_no_chord_and_unknown_have_no_root(label):
    parsed = parse_chord(label)
    assert parsed.is_no_chord
    assert parsed.root is None
    assert parsed.root_pc is None
    assert parsed.intervals == frozenset()
    assert parsed.bass_interval is None
    assert parsed.bass_pc is None


@pytest.mark.parametrize(
    ("label", "bass_pc"),
    [("D:min7", 2), ("D:min7/b7", 0), ("C:maj/3", 4), ("Bb:maj/5", 5)],
)
def test_bass_pc_is_an_absolute_pitch_class(label, bass_pc):
    assert parse_chord(label).bass_pc == bass_pc


@pytest.mark.parametrize("label", ["", "H:maj", "C:foo", "c:maj", "C:b9"])
def test_invalid_labels_raise(label):
    with pytest.raises(InvalidChordLabelError, match="Invalid chord label"):
        parse_chord(label)


def test_parsed_chord_is_immutable():
    parsed = parse_chord("C:maj")
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.root = "D"
