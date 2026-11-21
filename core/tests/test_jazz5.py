import pytest

from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5, classify, extension_intervals, extension_names


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("C:maj", Jazz5.MAJ),
        ("C:maj7", Jazz5.MAJ),
        ("C:maj6", Jazz5.MAJ),
        ("C:maj9", Jazz5.MAJ),
        ("C:aug", Jazz5.MAJ),
        ("C:min", Jazz5.MIN),
        ("C:min7", Jazz5.MIN),
        ("C:min6", Jazz5.MIN),
        ("C:minmaj7", Jazz5.MIN),
        ("C:min11", Jazz5.MIN),
        ("C:min7(*5)", Jazz5.MIN),
        ("C:7", Jazz5.DOM7),
        ("C:9", Jazz5.DOM7),
        ("C:13", Jazz5.DOM7),
        ("C:7(b9)", Jazz5.DOM7),
        ("C:7(#9)", Jazz5.DOM7),
        ("C:7(*5)", Jazz5.DOM7),
        ("C:sus4(b7)", Jazz5.DOM7),
        ("C:hdim7", Jazz5.HDIM7),
        ("C:dim", Jazz5.DIM),
        ("C:dim7", Jazz5.DIM),
        ("C:sus4", None),
        ("C:sus2", None),
        ("C:5", None),
        ("C:1", None),
    ],
)
def test_classify(label, expected):
    assert classify(parse_chord(label).intervals) is expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("C:maj", ()),
        ("C:maj7", ("7",)),
        ("C:maj6", ("6",)),
        ("C:maj9", ("7", "9")),
        ("C:maj7(#11)", ("7", "#11")),
        ("C:maj7(*5,b5)", ("b5", "7")),
        ("C:aug", ("#5",)),
        ("D:min7", ("b7",)),
        ("C:min6", ("6",)),
        ("C:minmaj7", ("7",)),
        ("C:min11", ("b7", "9", "11")),
        ("C:7", ()),
        ("C:7(b9)", ("b9",)),
        ("C:7(#9)", ("#9",)),
        ("C:13", ("9", "11", "13")),
        ("C:7(b13)", ("b13",)),
        ("C:7(*5,b13)", ("#5",)),
        ("C:hdim7", ()),
        ("C:dim7", ("bb7",)),
        ("C:sus4", ("4", "5")),
        ("C:sus2", ("2", "5")),
        ("C:sus4(b7)", ("4",)),
        ("C:sus4(b7,9)", ("4", "9")),
    ],
)
def test_extension_names(label, expected):
    intervals = parse_chord(label).intervals
    assert extension_names(intervals, classify(intervals)) == expected


def test_extension_intervals_are_the_tones_outside_the_core():
    ninth = parse_chord("C:9").intervals
    assert extension_intervals(ninth, Jazz5.DOM7) == frozenset({2})


def test_extension_intervals_without_a_class_keep_everything_but_the_root():
    sus = parse_chord("C:sus4").intervals
    assert extension_intervals(sus, None) == frozenset({5, 7})


def test_omitted_tones_are_not_extensions():
    no_fifth = parse_chord("C:7(*5)").intervals
    assert extension_intervals(no_fifth, Jazz5.DOM7) == frozenset()
