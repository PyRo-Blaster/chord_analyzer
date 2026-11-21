import pytest

from jca_core.chords.agreement import Agreement, agreement_level
from jca_core.chords.harte import parse_chord


def level(first: str, second: str) -> Agreement:
    return agreement_level(parse_chord(first), parse_chord(second))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("D:min7", "D:min7"),
        ("C#:maj", "Db:maj"),
        ("C:maj/3", "C:maj"),
        ("C:7(*5)", "C:7"),
        ("N", "N"),
        ("N", "X"),
    ],
)
def test_level_a_same_root_class_and_extensions(first, second):
    assert level(first, second) is Agreement.A


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:9", "C:7"), ("C:maj7", "C:maj"), ("D:min7", "D:min"), ("G:7(b9)", "G:7")],
)
def test_level_b_same_root_and_class_different_extensions(first, second):
    assert level(first, second) is Agreement.B


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:maj7", "C:7"), ("C:min7", "C:maj"), ("B:hdim7", "B:dim"), ("C:sus4", "C:maj")],
)
def test_level_c_same_root_different_class(first, second):
    assert level(first, second) is Agreement.C


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:maj", "G:maj"), ("A:min7", "C:maj6"), ("C:maj", "N"), ("N", "C:maj")],
)
def test_level_d_different_root(first, second):
    assert level(first, second) is Agreement.D


def test_agreement_does_not_depend_on_the_order():
    assert level("C:9", "C:7") is level("C:7", "C:9")
