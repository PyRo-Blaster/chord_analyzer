import json

import pytest

from jca_core.chords.harte import parse_chord
from jca_core.chords.parts import chord_parts
from jca_core.decoder.draft import decode
from jca_core.export.json_export import analysis_from_json, analysis_to_json
from jca_core.grid.beats import regular_beat_grid
from jca_core.schema.records import AnalysisDocument, ChordSegment

GRID = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
LV = (ChordSegment(start=0.0, end=2.0, label="D:min7"),)
BTC = (ChordSegment(start=0.0, end=2.0, label="D:min"),)


def document() -> AnalysisDocument:
    chart = decode(GRID, LV, BTC, (2, None, None, None))
    return AnalysisDocument(beats=GRID, lv_chordia=LV, btc=BTC, chart=chart)


def test_json_round_trip_gives_the_same_document():
    original = document()
    assert analysis_from_json(analysis_to_json(original)) == original


def test_json_holds_times_beats_both_models_and_the_edits():
    data = json.loads(analysis_to_json(document()))
    assert data["schema_version"] == 1
    assert data["beats"][0] == {"time": 0.0, "bar": 1, "beat": 1}
    assert data["lv_chordia"] == [{"start": 0.0, "end": 2.0, "label": "D:min7"}]
    assert data["btc"] == [{"start": 0.0, "end": 2.0, "label": "D:min"}]
    assert data["chart"][0]["draft"]["class"] == "min"
    assert data["chart"][0]["user_edit"] is None


def test_a_user_edit_survives_the_round_trip():
    original = document()
    edit = chord_parts(parse_chord("D:min9"))
    edited_chart = (original.chart[0].model_copy(update={"user_edit": edit}), *original.chart[1:])
    edited = original.model_copy(update={"chart": edited_chart})
    restored = analysis_from_json(analysis_to_json(edited))
    assert restored.chart[0].user_edit == edit
    assert restored.chart[0].draft == original.chart[0].draft


@pytest.mark.parametrize("text", ["", "not json", "{}", '{"beats": []}'])
def test_invalid_json_raises_a_clear_error(text):
    with pytest.raises(ValueError, match="Invalid analysis JSON"):
        analysis_from_json(text)
