import pytest

from jca_core.grid.beats import beat_boundaries, build_beat_grid, regular_beat_grid


def numbers(grid):
    return [(beat.bar, beat.beat) for beat in grid]


def test_regular_grid_numbers_bars_and_beats():
    times = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    grid = regular_beat_grid(times, beats_per_bar=4)
    assert numbers(grid) == [(1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2)]
    assert [beat.time for beat in grid] == times


def test_regular_grid_with_pickup_beats():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5, 2.0], beats_per_bar=3, first_downbeat_index=2)
    assert numbers(grid) == [(0, 1), (0, 2), (1, 1), (1, 2), (1, 3)]


def test_grid_from_tracker_downbeats_uses_the_nearest_beat():
    grid = build_beat_grid([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0], downbeat_times=[0.52, 2.01])
    assert numbers(grid) == [(0, 1), (1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]


def test_grid_from_tracker_needs_a_downbeat():
    with pytest.raises(ValueError, match="downbeat"):
        build_beat_grid([0.0, 0.5], downbeat_times=[])


@pytest.mark.parametrize("times", [[], [0.0, 0.5, 0.5], [1.0, 0.5]])
def test_beat_times_must_be_present_and_increasing(times):
    with pytest.raises(ValueError, match="[Bb]eat"):
        regular_beat_grid(times, beats_per_bar=4)


def test_beats_per_bar_must_be_positive():
    with pytest.raises(ValueError, match="beats_per_bar"):
        regular_beat_grid([0.0, 0.5], beats_per_bar=0)


@pytest.mark.parametrize("index", [-1, 2])
def test_first_downbeat_index_must_point_at_a_beat(index):
    with pytest.raises(ValueError, match="first_downbeat_index"):
        regular_beat_grid([0.0, 0.5], beats_per_bar=4, first_downbeat_index=index)


def test_boundaries_add_one_edge_after_the_last_beat():
    grid = regular_beat_grid([0.0, 0.5, 1.0], beats_per_bar=4)
    assert beat_boundaries(grid) == (0.0, 0.5, 1.0, 1.5)


def test_boundaries_of_a_single_beat_use_the_default_length():
    grid = regular_beat_grid([2.0], beats_per_bar=4)
    assert beat_boundaries(grid) == (2.0, 2.5)


def test_boundaries_need_a_beat():
    with pytest.raises(ValueError, match="At least one beat"):
        beat_boundaries([])
