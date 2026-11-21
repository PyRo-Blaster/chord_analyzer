import pytest
from hypothesis import given
from hypothesis import strategies as st

from jca_core.grid.beats import beat_boundaries, regular_beat_grid
from jca_core.grid.snap import snap_segments, snap_time
from jca_core.schema.records import ChordSegment

BEAT_SECONDS = 0.5
# Two bars of 4/4 at 120 BPM: beats at 0.0 to 3.5, bar lines at 0.0 and 2.0, end at 4.0.
GRID = regular_beat_grid([index * BEAT_SECONDS for index in range(8)], beats_per_bar=4)


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        (0.2, 0.0),
        (0.3, 0.5),
        (0.6, 0.5),
        (1.8, 2.0),
        (3.9, 4.0),
        (99.0, 4.0),
    ],
)
def test_snap_time_moves_to_the_nearest_beat(time, expected):
    assert snap_time(time, GRID) == expected


@pytest.mark.parametrize("time", [1.75, 2.25])
def test_a_change_half_a_beat_from_a_bar_line_moves_to_the_bar_line(time):
    assert snap_time(time, GRID) == 2.0


def test_a_tie_between_two_ordinary_beats_moves_to_the_earlier_beat():
    assert snap_time(0.75, GRID) == 0.5


def test_time_before_the_grid_moves_to_the_first_beat():
    late_grid = regular_beat_grid([1.0, 1.5, 2.0], beats_per_bar=4)
    assert snap_time(0.1, late_grid) == 1.0


def test_an_anticipated_change_lands_on_the_bar_line():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    assert snap_segments(segments, GRID) == (seg(0.0, 2.0, "D:min7"), seg(2.0, 4.0, "G:7"))


def test_a_segment_shorter_than_a_beat_is_removed_and_its_neighbours_merge():
    segments = [seg(0.0, 1.9, "C:maj"), seg(1.9, 2.1, "F:maj"), seg(2.1, 4.0, "C:maj")]
    assert snap_segments(segments, GRID) == (seg(0.0, 4.0, "C:maj"),)


def test_segments_are_put_in_time_order():
    segments = [seg(2.0, 4.0, "G:7"), seg(0.0, 2.0, "D:min7")]
    assert snap_segments(segments, GRID) == (seg(0.0, 2.0, "D:min7"), seg(2.0, 4.0, "G:7"))


def test_snap_segments_does_not_change_its_input():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    snap_segments(segments, GRID)
    assert segments == [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]


@given(st.floats(min_value=0.0, max_value=4.0))
def test_a_change_inside_the_grid_never_moves_more_than_half_a_beat(time):
    snapped = snap_time(time, GRID)
    assert snapped in beat_boundaries(GRID)
    assert abs(snapped - time) <= BEAT_SECONDS / 2 + 1e-9
