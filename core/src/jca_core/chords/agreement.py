"""Agreement level between the labels of two chord models."""

from enum import StrEnum

from jca_core.chords.harte import ParsedChord
from jca_core.chords.jazz5 import classify, extension_intervals


class Agreement(StrEnum):
    A = "A"  # same root, same class, same extensions
    B = "B"  # same root and class, different extensions
    C = "C"  # same root, different class
    D = "D"  # different root


def agreement_level(first: ParsedChord, second: ParsedChord) -> Agreement:
    """Compare two labels. The bass note is ignored, and two no-chord labels agree."""
    if first.root_pc != second.root_pc:
        return Agreement.D
    first_class = classify(first.intervals)
    second_class = classify(second.intervals)
    if first_class != second_class:
        return Agreement.C
    first_extensions = extension_intervals(first.intervals, first_class)
    second_extensions = extension_intervals(second.intervals, second_class)
    return Agreement.A if first_extensions == second_extensions else Agreement.B
