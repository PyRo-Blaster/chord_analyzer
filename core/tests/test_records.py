import pytest
from pydantic import ValidationError

from jca_core.schema.records import (
    SCHEMA_VERSION,
    AnalysisDocument,
    Beat,
    ChartRecord,
    ChordSegment,
)

DESIGN_EXAMPLE = {
    "bar": 9,
    "beat": 1,
    "time": 14.62,
    "lv_chordia": "D:min7",
    "btc": "D:min7",
    "bass_pitch_class": "D",
    "agreement": "A",
    "draft": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
    "confidence": 0.8,
    "user_edit": None,
}


def test_the_chart_record_of_the_design_validates_and_round_trips():
    record = ChartRecord.model_validate(DESIGN_EXAMPLE)
    dumped = record.model_dump(mode="json")
    assert {key: dumped[key] for key in DESIGN_EXAMPLE} == DESIGN_EXAMPLE
    assert dumped["extensions_confidence"] == 0.0
    assert dumped["needs_review"] is False


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_must_be_between_zero_and_one(confidence):
    with pytest.raises(ValidationError):
        ChartRecord.model_validate({**DESIGN_EXAMPLE, "confidence": confidence})


def test_agreement_must_be_a_known_level():
    with pytest.raises(ValidationError):
        ChartRecord.model_validate({**DESIGN_EXAMPLE, "agreement": "E"})


def test_segment_end_must_not_be_before_start():
    with pytest.raises(ValidationError, match="end must not be before start"):
        ChordSegment(start=2.0, end=1.0, label="C:maj")


def test_segment_label_must_not_be_empty():
    with pytest.raises(ValidationError):
        ChordSegment(start=0.0, end=1.0, label="")


@pytest.mark.parametrize("fields", [{"bar": -1}, {"beat": 0}, {"time": -0.5}])
def test_beat_rejects_impossible_numbers(fields):
    with pytest.raises(ValidationError):
        Beat(**{"time": 0.0, "bar": 1, "beat": 1, **fields})


def test_analysis_document_carries_a_schema_version():
    document = AnalysisDocument(beats=(), lv_chordia=(), btc=(), chart=())
    assert document.schema_version == SCHEMA_VERSION == 1


def test_records_are_immutable():
    beat = Beat(time=0.0, bar=1, beat=1)
    with pytest.raises(ValidationError):
        beat.time = 1.0
