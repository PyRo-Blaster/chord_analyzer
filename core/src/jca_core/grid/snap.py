"""Snap chord changes to the beat grid (decoder steps 1 and 2 of the design)."""

from bisect import bisect_left
from collections.abc import Sequence
from functools import reduce

from jca_core.grid.beats import beat_boundaries
from jca_core.schema.records import Beat, ChordSegment

TIE_TOLERANCE_SECONDS = 1e-6


def snap_time(time: float, beats: Sequence[Beat]) -> float:
    """Move a time to the nearest beat. A tie goes to a bar line, or else to the earlier beat."""
    return _snap(time, beat_boundaries(beats), _bar_lines(beats))


def snap_segments(
    segments: Sequence[ChordSegment], beats: Sequence[Beat]
) -> tuple[ChordSegment, ...]:
    """Snap both ends of each segment, drop segments with no length, merge equal neighbours."""
    edges = beat_boundaries(beats)
    bar_lines = _bar_lines(beats)
    ordered = sorted(segments, key=lambda segment: segment.start)
    snapped = (
        (_snap(segment.start, edges, bar_lines), _snap(segment.end, edges, bar_lines), segment)
        for segment in ordered
    )
    kept = (
        ChordSegment(start=start, end=end, label=segment.label)
        for start, end, segment in snapped
        if end > start
    )
    return reduce(_append_or_merge, kept, ())


def _bar_lines(beats: Sequence[Beat]) -> frozenset[float]:
    return frozenset(beat.time for beat in beats if beat.bar >= 1 and beat.beat == 1)


def _snap(time: float, edges: tuple[float, ...], bar_lines: frozenset[float]) -> float:
    index = bisect_left(edges, time)
    candidates = edges[max(0, index - 1) : index + 1]
    nearest = min(abs(time - edge) for edge in candidates)
    tied = tuple(
        edge for edge in candidates if abs(time - edge) - nearest <= TIE_TOLERANCE_SECONDS
    )
    on_bar_line = tuple(edge for edge in tied if edge in bar_lines)
    return (on_bar_line or tied)[0]


def _append_or_merge(
    merged: tuple[ChordSegment, ...], segment: ChordSegment
) -> tuple[ChordSegment, ...]:
    if merged and merged[-1].label == segment.label and merged[-1].end == segment.start:
        joined = ChordSegment(start=merged[-1].start, end=segment.end, label=segment.label)
        return (*merged[:-1], joined)
    return (*merged, segment)
