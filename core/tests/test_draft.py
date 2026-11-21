import pytest

from jca_core.chords.agreement import Agreement
from jca_core.decoder.draft import decode
from jca_core.grid.beats import regular_beat_grid
from jca_core.schema.records import ChordSegment

# Two bars of 4/4 at 120 BPM.
GRID = regular_beat_grid([index * 0.5 for index in range(8)], beats_per_bar=4)
NO_BASS = (None,) * 8


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


def whole(label: str) -> list[ChordSegment]:
    return [seg(0.0, 4.0, label)]


def test_agreeing_models_give_the_chart_record_of_the_design():
    records = decode(GRID, whole("D:min7"), whole("D:min7"), (2,) * 8)
    assert len(records) == 8
    assert records[0].model_dump(mode="json") == {
        "bar": 1,
        "beat": 1,
        "time": 0.0,
        "lv_chordia": "D:min7",
        "btc": "D:min7",
        "bass_pitch_class": "D",
        "agreement": "A",
        "draft": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
        "confidence": 0.8,
        "extensions_confidence": 0.6,
        "needs_review": False,
        "user_edit": None,
    }


def test_different_extensions_keep_the_primary_label_at_level_b():
    record = decode(GRID, whole("G:9"), whole("G:7"), NO_BASS)[0]
    assert record.agreement is Agreement.B
    assert record.draft.extensions == ("9",)
    assert record.confidence == 0.7
    assert record.extensions_confidence == 0.3
    assert record.needs_review is False


@pytest.mark.parametrize(
    ("btc_label", "level", "confidence"),
    [("C:7", Agreement.C, 0.4), ("F:maj7", Agreement.D, 0.2)],
)
def test_levels_c_and_d_are_marked_for_review(btc_label, level, confidence):
    record = decode(GRID, whole("C:maj7"), whole(btc_label), NO_BASS)[0]
    assert record.agreement is level
    assert record.confidence == confidence
    assert record.needs_review is True
    assert record.draft.root == "C"


def test_a_bass_note_that_fits_neither_model_marks_the_whole_bar():
    bass = (6, None, None, None, 0, None, None, None)  # F# on beat 1 of bar 1, C in bar 2
    records = decode(GRID, whole("C:maj"), whole("C:maj"), bass)
    assert [record.needs_review for record in records] == [True] * 4 + [False] * 4
    assert [record.confidence for record in records] == [0.6] * 4 + [0.8] * 4
    assert records[0].bass_pitch_class == "F#"


def test_a_bass_note_on_the_slash_bass_passes_the_check():
    bass = (4,) + (None,) * 7  # E under C/E
    records = decode(GRID, whole("C:maj/3"), whole("C:maj"), bass)
    assert records[0].needs_review is False


def test_a_bass_note_off_beat_one_is_not_checked():
    bass = (None, 6, 6, 6, None, 6, 6, 6)
    records = decode(GRID, whole("C:maj"), whole("C:maj"), bass)
    assert not any(record.needs_review for record in records)


def test_no_chordal_instrument_halves_the_confidence():
    record = decode(GRID, whole("C:maj"), whole("C:maj"), NO_BASS, has_chordal_instrument=False)[0]
    assert record.confidence == 0.4
    assert record.extensions_confidence == 0.3


def test_the_primary_model_can_be_btc():
    record = decode(GRID, whole("G:9"), whole("G:7"), NO_BASS, primary="btc")[0]
    assert record.draft.extensions == ()


def test_an_anticipated_change_starts_on_the_bar_line():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    records = decode(GRID, segments, segments, NO_BASS)
    assert [record.lv_chordia for record in records] == ["D:min7"] * 4 + ["G:7"] * 4


def test_a_segment_shorter_than_a_beat_does_not_reach_the_chart():
    segments = [seg(0.0, 1.9, "C:maj"), seg(1.9, 2.1, "F:maj"), seg(2.1, 4.0, "C:maj")]
    records = decode(GRID, segments, segments, NO_BASS)
    assert {record.lv_chordia for record in records} == {"C:maj"}


def test_beats_that_a_model_does_not_cover_are_no_chord():
    records = decode(GRID, [seg(0.0, 2.0, "C:maj")], whole("C:maj"), NO_BASS)
    assert records[4].lv_chordia == "N"
    assert records[4].agreement is Agreement.D
    assert records[4].draft.root is None


def test_the_bass_list_must_match_the_grid():
    with pytest.raises(ValueError, match="one bass pitch class for each beat"):
        decode(GRID, whole("C:maj"), whole("C:maj"), (None,) * 3)
