"""Note names and pitch-class numbers (C is 0, B is 11)."""

import re
from typing import Literal

PITCH_CLASS_COUNT = 12

Spelling = Literal["default", "sharp", "flat"]

_NATURALS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_PATTERN = re.compile(r"[A-G][#b]*")
_NAMES: dict[str, tuple[str, ...]] = {
    "default": ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"),
    "sharp": ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
    "flat": ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"),
}


def pitch_class_number(name: str) -> int:
    """Return 0 to 11 for a note name such as "C", "F#" or "Bb"."""
    if not _NOTE_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid note name: {name!r}")
    return (_NATURALS[name[0]] + name.count("#") - name.count("b")) % PITCH_CLASS_COUNT


def pitch_class_name(number: int, spelling: Spelling = "default") -> str:
    """Return the note name for a pitch-class number."""
    if not 0 <= number < PITCH_CLASS_COUNT:
        raise ValueError(f"Pitch class must be 0 to 11, got {number}")
    return _NAMES[spelling][number]


def spelling_of(name: str) -> Spelling:
    """Return the spelling family of a note name, so that related notes match it."""
    if "#" in name:
        return "sharp"
    if "b" in name:
        return "flat"
    return "default"
