import pytest

from jca_core.chords.display import chord_symbol
from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5
from jca_core.chords.parts import ChordParts, chord_parts


@pytest.mark.parametrize(
    ("label", "symbol"),
    [
        ("C:maj", "C"),
        ("C", "C"),
        ("C:maj7", "Cmaj7"),
        ("C:maj9", "Cmaj9"),
        ("C:maj6", "C6"),
        ("C:maj(9)", "Cadd9"),
        ("C:maj7(#11)", "Cmaj7#11"),
        ("C:maj(#11)", "C(#11)"),
        ("C:aug", "C+"),
        ("C:min", "Cm"),
        ("D:min7", "Dm7"),
        ("C:min9", "Cm9"),
        ("C:min11", "Cm11"),
        ("C:min6", "Cm6"),
        ("F#:minmaj7", "F#m(maj7)"),
        ("G:7", "G7"),
        ("G:7(b9)", "G7b9"),
        ("C:7(#9)", "C7#9"),
        ("Db:7(b13)", "Db7b13"),
        ("C:9", "C9"),
        ("C:13", "C13"),
        ("C:sus4(b7)", "C7sus4"),
        ("C:sus4(b7,9)", "C9sus4"),
        ("B:hdim7", "Bm7b5"),
        ("C:dim", "Cdim"),
        ("C:dim7", "Cdim7"),
        ("C:sus4", "Csus4"),
        ("C:sus2", "Csus2"),
        ("C:5", "C5"),
        ("C:1", "C"),
        ("C:maj/3", "C/E"),
        ("D:min7/b7", "Dm7/C"),
        ("Bb:maj/5", "Bb/F"),
        ("N", "N.C."),
        ("X", "N.C."),
    ],
)
def test_chord_symbol_from_a_label(label, symbol):
    assert chord_symbol(chord_parts(parse_chord(label))) == symbol


def test_chord_symbol_from_edited_parts():
    edited = ChordParts(root="G", chord_class=Jazz5.DOM7, extensions=("b9", "13"), bass="G")
    assert chord_symbol(edited) == "G13b9"


def test_additions_to_a_plain_triad_go_in_brackets():
    edited = ChordParts(root="C", chord_class=Jazz5.MIN, extensions=("11",))
    assert chord_symbol(edited) == "Cm(11)"
