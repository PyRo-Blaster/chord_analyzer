"""Build the beat grid: a time, a bar number and a beat number for each beat."""

from collections.abc import Sequence
from itertools import accumulate, pairwise

from jca_core.schema.records import Beat

DEFAULT_BEAT_SECONDS = 0.5


def regular_beat_grid(
    beat_times: Sequence[float], beats_per_bar: int, first_downbeat_index: int = 0
) -> tuple[Beat, ...]:
    """Number the beats from a time signature and the index of the first downbeat."""
    _check_times(beat_times)
    if beats_per_bar < 1:
        raise ValueError(f"beats_per_bar must be at least 1, got {beats_per_bar}")
    if not 0 <= first_downbeat_index < len(beat_times):
        raise ValueError(f"first_downbeat_index must point at a beat, got {first_downbeat_index}")
    flags = tuple(
        index >= first_downbeat_index and (index - first_downbeat_index) % beats_per_bar == 0
        for index in range(len(beat_times))
    )
    return _numbered(beat_times, flags)


def build_beat_grid(
    beat_times: Sequence[float], downbeat_times: Sequence[float]
) -> tuple[Beat, ...]:
    """Number the beats from tracker downbeats. Each downbeat marks its nearest beat."""
    _check_times(beat_times)
    if len(downbeat_times) == 0:
        raise ValueError("At least one downbeat is required")
    marked = frozenset(
        min(range(len(beat_times)), key=lambda index: abs(beat_times[index] - downbeat))
        for downbeat in downbeat_times
    )
    flags = tuple(index in marked for index in range(len(beat_times)))
    return _numbered(beat_times, flags)


def beat_boundaries(beats: Sequence[Beat]) -> tuple[float, ...]:
    """Return the beat times plus one closing edge, so that the last beat has a length."""
    times = tuple(beat.time for beat in beats)
    if not times:
        raise ValueError("At least one beat is required")
    last_length = times[-1] - times[-2] if len(times) > 1 else DEFAULT_BEAT_SECONDS
    return (*times, times[-1] + last_length)


def _check_times(beat_times: Sequence[float]) -> None:
    if len(beat_times) == 0:
        raise ValueError("At least one beat is required")
    if any(later <= earlier for earlier, later in pairwise(beat_times)):
        raise ValueError("Beat times must be strictly increasing")


def _next_position(position: tuple[int, int], is_downbeat: bool) -> tuple[int, int]:
    bar, beat = position
    return (bar + 1, 1) if is_downbeat else (bar, beat + 1)


def _numbered(beat_times: Sequence[float], downbeat_flags: Sequence[bool]) -> tuple[Beat, ...]:
    positions = tuple(accumulate(downbeat_flags, _next_position, initial=(0, 0)))[1:]
    return tuple(
        Beat(time=time, bar=bar, beat=beat)
        for time, (bar, beat) in zip(beat_times, positions, strict=True)
    )
