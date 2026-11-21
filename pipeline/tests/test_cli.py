import shutil

import pytest
from jca_core.separation.plan import Instrument

from jca_pipeline.cli import format_stage, main, parse_horn_counts, parse_instruments
from jca_pipeline.state import StageRecord, WorkerMetric

from .fakes import FakeRunner
from .synth import make_track

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def test_parse_instruments_accepts_names_in_any_case_and_spacing():
    assert parse_instruments(" Piano, double bass ,DRUMS") == (
        Instrument.PIANO,
        Instrument.DOUBLE_BASS,
        Instrument.DRUMS,
    )


def test_parse_instruments_names_the_valid_choices():
    with pytest.raises(ValueError, match="Unknown instrument 'banjo'.*double bass"):
        parse_instruments("piano,banjo")


def test_parse_instruments_needs_at_least_one():
    with pytest.raises(ValueError, match="at least one instrument"):
        parse_instruments(" , ")


def test_parse_horn_counts():
    assert parse_horn_counts(["trumpet=2", "Alto Sax=3"]) == {
        Instrument.TRUMPET: 2,
        Instrument.ALTO_SAX: 3,
    }


@pytest.mark.parametrize("text", ["trumpet", "trumpet=two", "banjo=2"])
def test_parse_horn_counts_rejects_bad_values(text):
    with pytest.raises(ValueError):
        parse_horn_counts([text])


def test_format_stage_shows_time_memory_and_cache():
    metric = WorkerMetric(
        worker="chords_btc", seconds=7.2, peak_memory_bytes=700_000_000, device="cpu"
    )
    record = StageRecord(stage="recognising", key="k", outputs={}, seconds=8.0, workers=(metric,))
    assert format_stage(record) == (
        "recognising   ran      8.0 s\n    chords_btc             7.2 s   0.70 GB  cpu"
    )
    assert format_stage(record.model_copy(update={"cached": True})).startswith(
        "recognising   cached"
    )


@needs_ffmpeg
def test_main_runs_the_pipeline_and_prints_the_chart(tmp_path, capsys):
    track = make_track(tmp_path / "upload")
    argv = [str(track.mix_path), "--instruments", "piano,double bass,drums"]
    argv += ["--out", str(tmp_path / "runs")]
    code = main(argv, runner=FakeRunner(track))
    printed = capsys.readouterr().out
    assert code == 0
    assert "separating    ran" in printed
    assert "| Dm7   | G7    | Cmaj7 | Cmaj7 |" in printed
    assert "analysis.json" in printed


@needs_ffmpeg
def test_main_prints_warnings(tmp_path, capsys):
    track = make_track(tmp_path / "upload")
    argv = [str(track.mix_path), "--instruments", "piano,double bass,drums,trumpet"]
    argv += ["--out", str(tmp_path / "runs")]
    assert main(argv, runner=FakeRunner(track)) == 0
    assert "Warning: No separation model is available for trumpet" in capsys.readouterr().out


@needs_ffmpeg
def test_main_reports_a_worker_failure(tmp_path, capsys):
    track = make_track(tmp_path / "upload")
    argv = [str(track.mix_path), "--instruments", "piano", "--out", str(tmp_path / "runs")]
    code = main(argv, runner=FakeRunner(track, fail=frozenset({"beats_beatthis"})))
    error = capsys.readouterr().err
    assert code == 1
    assert "Error: tracking failed: beats_beatthis: model exploded" in error
    assert "Traceback: boom" in error


def test_main_reports_a_bad_instrument(tmp_path, capsys):
    code = main([str(tmp_path / "a.wav"), "--instruments", "banjo"], runner=None)
    assert code == 1
    assert "Unknown instrument 'banjo'" in capsys.readouterr().err


def test_main_reports_a_missing_file(tmp_path, capsys):
    code = main([str(tmp_path / "missing.wav"), "--instruments", "piano"], runner=None)
    assert code == 1
    assert "missing.wav" in capsys.readouterr().err


def test_main_reports_a_moved_downbeat_without_a_time_signature(tmp_path, capsys):
    argv = [str(tmp_path / "a.wav"), "--instruments", "piano", "--first-downbeat", "2"]
    assert main(argv, runner=None) == 1
    assert "beats_per_bar" in capsys.readouterr().err
