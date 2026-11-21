import json

import pytest

from jca_pipeline.adapters import (
    AdapterError,
    beats_from_tracker,
    segments_from_btc,
    segments_from_lv_chordia,
)
from jca_core.schema.records import ChordSegment


def write(tmp_path, data, name="raw.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_lv_chordia_fixture_parses(phase0_fixtures):
    parsed = segments_from_lv_chordia(phase0_fixtures / "synth60.lv_chordia.json")
    assert parsed.warnings == ()
    assert len(parsed.segments) == 31
    assert parsed.segments[1] == ChordSegment(start=0.02, end=2.02, label="D:min7")
    assert all(segment.end > segment.start for segment in parsed.segments)


def test_btc_fixture_parses(phase0_fixtures):
    parsed = segments_from_btc(phase0_fixtures / "synth60.btc.json")
    assert parsed.warnings == ()
    assert parsed.segments[0] == ChordSegment(start=0.0, end=1.944, label="F:maj7")


def test_tracker_fixture_parses(phase0_fixtures):
    beats, downbeats = beats_from_tracker(phase0_fixtures / "synth60.beats.json")
    assert (len(beats), len(downbeats)) == (121, 31)
    assert beats[:2] == (0.02, 0.5)


def test_invalid_label_becomes_unknown_with_a_warning(tmp_path):
    raw = [
        {"start": 0.0, "end": 1.0, "chord": "C:maj"},
        {"start": 1.0, "end": 2.0, "chord": "C:weird"},
    ]
    parsed = segments_from_btc(write(tmp_path, raw))
    assert [segment.label for segment in parsed.segments] == ["C:maj", "X"]
    assert parsed.warnings == ("BTC label 'C:weird' is not valid Harte notation; read as X",)


def test_each_invalid_label_is_warned_once(tmp_path):
    raw = [{"start_time": i, "end_time": i + 1, "chord": "C:weird"} for i in range(3)]
    assert len(segments_from_lv_chordia(write(tmp_path, raw)).warnings) == 1


def test_zero_length_segments_are_dropped(tmp_path):
    raw = [{"start": 1.0, "end": 1.0, "chord": "N"}, {"start": 1.0, "end": 2.0, "chord": "G:7"}]
    assert segments_from_btc(write(tmp_path, raw)).segments == (
        ChordSegment(start=1.0, end=2.0, label="G:7"),
    )


def test_segments_are_put_in_time_order(tmp_path):
    raw = [
        {"start": 2.0, "end": 3.0, "chord": "G:7"},
        {"start": 0.0, "end": 2.0, "chord": "D:min7"},
    ]
    labels = [segment.label for segment in segments_from_btc(write(tmp_path, raw)).segments]
    assert labels == ["D:min7", "G:7"]


def test_beats_are_sorted_and_repeats_removed(tmp_path):
    raw = {"beats": [1.0, 0.5, 0.5, 1.5], "downbeats": [0.5, 0.5]}
    assert beats_from_tracker(write(tmp_path, raw)) == ((0.5, 1.0, 1.5), (0.5,))


@pytest.mark.parametrize(
    ("adapter", "data"),
    [
        (segments_from_btc, [{"start_time": 0, "end_time": 1, "chord": "C"}]),
        (segments_from_lv_chordia, [{"start": 0, "end": 1, "chord": "C"}]),
        (segments_from_btc, {"chord": "C"}),
        (segments_from_btc, [{"start": 2.0, "end": 1.0, "chord": "C"}]),
        (beats_from_tracker, {"beats": [0.5]}),
        (beats_from_tracker, {"beats": [], "downbeats": []}),
        (beats_from_tracker, {"beats": [-1.0, 0.5], "downbeats": [0.5]}),
    ],
)
def test_malformed_output_raises_a_clear_error(tmp_path, adapter, data):
    with pytest.raises(AdapterError, match="raw.json"):
        adapter(write(tmp_path, data))


def test_a_file_that_is_not_json_raises(tmp_path):
    path = tmp_path / "raw.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(AdapterError, match="not valid JSON"):
        segments_from_btc(path)


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(AdapterError, match="missing"):
        beats_from_tracker(tmp_path / "missing.json")
