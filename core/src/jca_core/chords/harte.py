"""Parse Harte chord labels (for example "D:min7/b7") with mir_eval."""

from dataclasses import dataclass
from functools import lru_cache

import mir_eval.chord

from jca_core.pitch import PITCH_CLASS_COUNT

NO_CHORD = "N"
PARSE_CACHE_SIZE = 4096


class InvalidChordLabelError(ValueError):
    """A label is not valid Harte notation."""


@dataclass(frozen=True)
class ParsedChord:
    """A chord label split into numbers.

    intervals: semitones above the root, in one octave, including 0 for the root.
    bass_interval: semitones from the root up to the bass note (0 in root position).
    A no-chord label ("N" or "X") has no root, no intervals and no bass.
    """

    label: str
    root: str | None
    root_pc: int | None
    intervals: frozenset[int]
    bass_interval: int | None

    @property
    def is_no_chord(self) -> bool:
        return self.root_pc is None

    @property
    def bass_pc(self) -> int | None:
        if self.root_pc is None or self.bass_interval is None:
            return None
        return (self.root_pc + self.bass_interval) % PITCH_CLASS_COUNT


@lru_cache(maxsize=PARSE_CACHE_SIZE)
def parse_chord(label: str) -> ParsedChord:
    """Parse one Harte label. Raises InvalidChordLabelError for a bad label."""
    try:
        root_number, bitmap, bass_number = mir_eval.chord.encode(
            label, reduce_extended_chords=True
        )
        root_name = mir_eval.chord.split(label, reduce_extended_chords=True)[0]
    except mir_eval.chord.InvalidChordException as error:
        raise InvalidChordLabelError(f"Invalid chord label: {label!r}") from error
    if root_number < 0:
        return ParsedChord(
            label=label, root=None, root_pc=None, intervals=frozenset(), bass_interval=None
        )
    return ParsedChord(
        label=label,
        root=root_name,
        root_pc=int(root_number),
        intervals=frozenset(index for index, present in enumerate(bitmap) if present),
        bass_interval=int(bass_number),
    )
