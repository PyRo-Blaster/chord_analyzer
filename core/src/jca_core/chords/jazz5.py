"""The five jazz chord classes of the JAAH paper, and names for the tones outside them."""

from enum import StrEnum

ROOT = 0
MINOR_THIRD = 3
MAJOR_THIRD = 4
DIMINISHED_FIFTH = 6
PERFECT_FIFTH = 7
MINOR_SEVENTH = 10
MAJOR_SEVENTH = 11


class Jazz5(StrEnum):
    MAJ = "maj"
    MIN = "min"
    DOM7 = "dom7"
    HDIM7 = "hdim7"
    DIM = "dim"


CORE_INTERVALS: dict[Jazz5, frozenset[int]] = {
    Jazz5.MAJ: frozenset({ROOT, MAJOR_THIRD, PERFECT_FIFTH}),
    Jazz5.MIN: frozenset({ROOT, MINOR_THIRD, PERFECT_FIFTH}),
    Jazz5.DOM7: frozenset({ROOT, MAJOR_THIRD, PERFECT_FIFTH, MINOR_SEVENTH}),
    Jazz5.HDIM7: frozenset({ROOT, MINOR_THIRD, DIMINISHED_FIFTH, MINOR_SEVENTH}),
    Jazz5.DIM: frozenset({ROOT, MINOR_THIRD, DIMINISHED_FIFTH}),
}

_PLAIN_NAMES = {
    1: "b9",
    2: "9",
    3: "#9",
    4: "3",
    5: "11",
    6: "#11",
    7: "5",
    8: "b13",
    9: "13",
    10: "b7",
    11: "7",
}
_NAME_ORDER = (
    "2", "3", "4", "b5", "5", "#5", "6", "bb7", "b7", "7",
    "b9", "9", "#9", "11", "#11", "b13", "13",
)  # fmt: skip


def classify(intervals: frozenset[int]) -> Jazz5 | None:
    """Return the Jazz5 class, or None for a chord that fits no class (sus, power chord)."""
    has_major_third = MAJOR_THIRD in intervals
    has_minor_seventh = MINOR_SEVENTH in intervals
    if MINOR_THIRD in intervals and not has_major_third:
        if DIMINISHED_FIFTH in intervals and PERFECT_FIFTH not in intervals:
            return Jazz5.HDIM7 if has_minor_seventh else Jazz5.DIM
        return Jazz5.MIN
    if has_major_third:
        return Jazz5.DOM7 if has_minor_seventh else Jazz5.MAJ
    return Jazz5.DOM7 if has_minor_seventh else None


def extension_intervals(intervals: frozenset[int], chord_class: Jazz5 | None) -> frozenset[int]:
    """Return the tones that are not core tones of the class."""
    core = CORE_INTERVALS[chord_class] if chord_class is not None else frozenset({ROOT})
    return intervals - core


def extension_names(intervals: frozenset[int], chord_class: Jazz5 | None) -> tuple[str, ...]:
    """Return the extension tones as degree names, in a fixed order."""
    names = {
        _extension_name(semitone, intervals, chord_class)
        for semitone in extension_intervals(intervals, chord_class)
    }
    return tuple(name for name in _NAME_ORDER if name in names)


def _extension_name(semitone: int, intervals: frozenset[int], chord_class: Jazz5 | None) -> str:
    has_third = bool(intervals & {MINOR_THIRD, MAJOR_THIRD})
    has_seventh = bool(intervals & {MINOR_SEVENTH, MAJOR_SEVENTH})
    has_fifth = PERFECT_FIFTH in intervals
    if semitone == 2 and not has_third and not has_seventh:
        return "2"
    if semitone == 5 and not has_third:
        return "4"
    if semitone == 6 and not has_fifth:
        return "b5"
    if semitone == 8 and not has_fifth:
        return "#5"
    if semitone == 9 and chord_class is Jazz5.DIM:
        return "bb7"
    if semitone == 9 and not has_seventh:
        return "6"
    return _PLAIN_NAMES[semitone]
