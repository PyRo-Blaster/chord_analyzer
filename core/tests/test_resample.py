from hypothesis import given
from hypothesis import strategies as st

from jca_core.grid.beats import regular_beat_grid
from jca_core.grid.resample import labels_per_beat
from jca_core.schema.records import ChordSegment

GRID = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
LABELS = ["C:maj", "D:min7", "G:7"]


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


def test_each_beat_takes_the_label_that_covers_it():
    segments = [seg(0.0, 1.0, "D:min7"), seg(1.0, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID) == ("D:min7", "D:min7", "G:7", "G:7")


def test_a_beat_with_two_labels_takes_the_longer_one():
    segments = [seg(0.0, 0.2, "C:maj"), seg(0.2, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID)[0] == "G:7"


def test_a_tie_takes_the_earlier_label():
    segments = [seg(0.0, 0.25, "C:maj"), seg(0.25, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID)[0] == "C:maj"


def test_a_beat_with_no_segment_is_no_chord():
    segments = [seg(0.0, 1.0, "C:maj")]
    assert labels_per_beat(segments, GRID) == ("C:maj", "C:maj", "N", "N")


def test_no_segments_give_no_chord_on_every_beat():
    assert labels_per_beat([], GRID) == ("N", "N", "N", "N")


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=3.0),
            st.floats(min_value=0.0, max_value=3.0),
            st.sampled_from(LABELS),
        ),
        max_size=12,
    )
)
def test_every_beat_gets_exactly_one_label(raw_segments):
    segments = [seg(start, start + length, label) for start, length, label in raw_segments]
    labels = labels_per_beat(segments, GRID)
    assert len(labels) == len(GRID)
    assert set(labels) <= {*LABELS, "N"}
