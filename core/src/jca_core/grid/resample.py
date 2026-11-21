"""Resample chord segments to the beat grid: one label for each beat."""

from collections.abc import Sequence
from itertools import pairwise

from jca_core.chords.harte import NO_CHORD
from jca_core.grid.beats import beat_boundaries
from jca_core.schema.records import Beat, ChordSegment


def labels_per_beat(segments: Sequence[ChordSegment], beats: Sequence[Beat]) -> tuple[str, ...]:
    """Return the label that covers most of each beat, or "N" where no segment does."""
    return tuple(
        _dominant_label(segments, start, end) for start, end in pairwise(beat_boundaries(beats))
    )


def _dominant_label(segments: Sequence[ChordSegment], start: float, end: float) -> str:
    overlaps = tuple(
        (min(segment.end, end) - max(segment.start, start), segment.label) for segment in segments
    )
    longest, label = max(overlaps, key=lambda overlap: overlap[0], default=(0.0, NO_CHORD))
    return label if longest > 0 else NO_CHORD
