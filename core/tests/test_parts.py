import pytest
from pydantic import ValidationError

from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5
from jca_core.chords.parts import NO_CHORD_PARTS, ChordParts, chord_parts


def test_matches_the_chart_record_in_the_design():
    parts = chord_parts(parse_chord("D:min7"))
    assert parts.model_dump(mode="json") == {
        "root": "D",
        "class": "min",
        "extensions": ["b7"],
        "bass": "D",
    }


@pytest.mark.parametrize(
    ("label", "bass"),
    [
        ("C:maj/3", "E"),
        ("D:min7/b7", "C"),
        ("Bb:maj/5", "F"),
        ("Eb:maj/3", "G"),
        ("Db:maj/5", "Ab"),
        ("F#:maj/3", "A#"),
    ],
)
def test_slash_bass_is_named_in_the_spelling_of_the_root(label, bass):
    assert chord_parts(parse_chord(label)).bass == bass


@pytest.mark.parametrize("label", ["N", "X"])
def test_no_chord_has_empty_parts(label):
    assert chord_parts(parse_chord(label)) == NO_CHORD_PARTS
    assert NO_CHORD_PARTS.model_dump(mode="json") == {
        "root": None,
        "class": None,
        "extensions": [],
        "bass": None,
    }


def test_chord_without_a_class():
    parts = chord_parts(parse_chord("G:sus4"))
    assert parts.chord_class is None
    assert parts.extensions == ("4", "5")


def test_accepts_the_field_name_and_the_alias():
    by_name = ChordParts(root="C", chord_class=Jazz5.MAJ)
    by_alias = ChordParts.model_validate({"root": "C", "class": "maj"})
    assert by_name == by_alias


def test_parts_are_immutable():
    parts = chord_parts(parse_chord("C:maj"))
    with pytest.raises(ValidationError):
        parts.root = "D"
