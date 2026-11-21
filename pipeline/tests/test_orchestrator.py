import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from jca_core.cache.key import file_sha256
from jca_core.export.json_export import analysis_from_json
from jca_core.separation.plan import Instrument

from jca_pipeline.audio import read_audio
from jca_pipeline.orchestrator import AnalysisRequest, PipelineError, analyze, run_dir_for
from jca_pipeline.state import STAGES, load_state

from .fakes import FakeRunner
from .synth import make_track

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

TRIO = (Instrument.PIANO, Instrument.DOUBLE_BASS, Instrument.DRUMS)
ALL_WORKERS = ["separate_bsroformer", "beats_beatthis", "chords_lvchordia", "chords_btc"]


@pytest.fixture
def track(tmp_path):
    return make_track(tmp_path / "upload")


def request(track, tmp_path, **fields) -> AnalysisRequest:
    return AnalysisRequest(
        **{"audio": track.mix_path, "instruments": TRIO, "out_root": tmp_path / "runs", **fields}
    )


def test_a_full_run_writes_every_stage(track, tmp_path):
    runner = FakeRunner(track)
    state = analyze(request(track, tmp_path), runner)
    assert [record.stage for record in state.stages] == list(STAGES)
    assert runner.workers_called() == ALL_WORKERS
    assert state.failure is None
    assert load_state(run_dir_for(tmp_path / "runs", state.track_sha256) / "state.json") == state


def test_the_chart_matches_the_known_chords(track, tmp_path):
    state = analyze(request(track, tmp_path), FakeRunner(track))
    chart = Path(state.record("decoded").outputs["chart"]).read_text(encoding="utf-8")
    assert chart == "| Dm7   | G7    | Cmaj7 | Cmaj7 |\n"
    document = analysis_from_json(
        Path(state.record("decoded").outputs["analysis"]).read_text(encoding="utf-8")
    )
    assert len(document.chart) == 16
    assert {record.agreement for record in document.chart} == {"A"}
    assert [record.bass_pitch_class for record in document.chart[::4]] == ["D", "G", "C", "C"]
    assert not any(record.needs_review for record in document.chart)


def test_stems_residue_and_drum_free_mix(track, tmp_path):
    outputs = analyze(request(track, tmp_path), FakeRunner(track)).record("separating").outputs
    assert set(outputs) == {
        "stem:drums", "stem:double bass", "stem:piano", "bass", "residue", "no_drums",
    }  # fmt: skip
    mix, rate = read_audio(track.mix_path)
    for key in ("stem:piano", "residue", "no_drums"):
        samples, stem_rate = read_audio(Path(outputs[key]))
        assert (samples.shape, stem_rate) == (mix.shape, rate)
    residue, _ = read_audio(Path(outputs["residue"]))
    assert float(np.max(np.abs(residue))) < 1e-4
    no_drums, _ = read_audio(Path(outputs["no_drums"]))
    np.testing.assert_allclose(no_drums, track.stems["piano"] + track.stems["bass"], atol=1e-5)
    assert outputs["bass"] == outputs["stem:double bass"]
    assert not list(Path(outputs["residue"]).parent.glob("raw*"))


def test_unnamed_separator_outputs_stay_in_the_residue(track, tmp_path):
    no_piano = (Instrument.DOUBLE_BASS, Instrument.DRUMS)
    state = analyze(request(track, tmp_path, instruments=no_piano), FakeRunner(track))
    outputs = state.record("separating").outputs
    assert "stem:piano" not in outputs
    residue, _ = read_audio(Path(outputs["residue"]))
    np.testing.assert_allclose(residue, track.stems["piano"], atol=1e-4)


def test_a_second_run_calls_no_worker(track, tmp_path):
    analyze(request(track, tmp_path), FakeRunner(track))
    runner = FakeRunner(track)
    state = analyze(request(track, tmp_path), runner)
    assert runner.workers_called() == []
    assert all(record.cached for record in state.stages)


def test_a_failed_stage_keeps_the_earlier_stages(track, tmp_path):
    with pytest.raises(PipelineError, match="recognising failed: chords_btc: model exploded"):
        analyze(request(track, tmp_path), FakeRunner(track, fail=frozenset({"chords_btc"})))
    run_dir = run_dir_for(tmp_path / "runs", file_sha256(track.mix_path))
    state = load_state(run_dir / "state.json")
    assert [record.stage for record in state.stages] == ["uploaded", "separating", "tracking"]
    assert state.failure.stage == "recognising"
    assert "Traceback: boom" in state.failure.log_tail
    runner = FakeRunner(track)
    analyze(request(track, tmp_path), runner)
    assert runner.workers_called() == ["chords_lvchordia", "chords_btc"]


def test_a_changed_instrument_list_reruns_separation_recognition_and_decoding(track, tmp_path):
    analyze(request(track, tmp_path), FakeRunner(track))
    runner = FakeRunner(track)
    quartet = (*TRIO, Instrument.TENOR_SAX)
    state = analyze(request(track, tmp_path, instruments=quartet), runner)
    assert runner.workers_called() == ["separate_bsroformer", "chords_lvchordia", "chords_btc"]
    assert state.record("tracking").cached
    assert not state.record("decoded").cached
    assert any("tenor sax" in warning for warning in state.record("separating").warnings)


def test_a_changed_time_signature_reruns_tracking_and_decoding_only(track, tmp_path):
    analyze(request(track, tmp_path), FakeRunner(track))
    runner = FakeRunner(track)
    state = analyze(request(track, tmp_path, beats_per_bar=2), runner)
    assert runner.workers_called() == ["beats_beatthis"]
    assert state.record("separating").cached and state.record("recognising").cached
    grid = json.loads(Path(state.record("tracking").outputs["grid"]).read_text())
    assert [beat["bar"] for beat in grid[:4]] == [1, 1, 2, 2]


def test_the_first_downbeat_can_be_moved(track, tmp_path):
    state = analyze(
        request(track, tmp_path, beats_per_bar=4, first_downbeat_index=1), FakeRunner(track)
    )
    grid = json.loads(Path(state.record("tracking").outputs["grid"]).read_text())
    assert [(beat["bar"], beat["beat"]) for beat in grid[:3]] == [(0, 1), (1, 1), (1, 2)]


def test_a_first_downbeat_without_a_time_signature_is_rejected(track, tmp_path):
    with pytest.raises(ValueError, match="beats_per_bar"):
        request(track, tmp_path, first_downbeat_index=1)


def test_disagreeing_models_are_marked_for_review(track, tmp_path):
    runner = FakeRunner(track, btc_labels=("F:maj7", "G:7", "C:maj7", "C:maj7"))
    state = analyze(request(track, tmp_path), runner)
    document = analysis_from_json(Path(state.record("decoded").outputs["analysis"]).read_text())
    assert [record.needs_review for record in document.chart[::4]] == [True, False, False, False]


def test_invalid_model_labels_become_warnings(track, tmp_path):
    runner = FakeRunner(track, lv_labels=("D:min7", "G:weird", "C:maj7", "C:maj7"))
    state = analyze(request(track, tmp_path), runner)
    assert state.record("recognising").warnings == (
        "lv-chordia label 'G:weird' is not valid Harte notation; read as X",
    )


def test_the_full_mix_can_feed_the_chord_models(track, tmp_path):
    runner = FakeRunner(track)
    analyze(request(track, tmp_path, chord_input="full_mix"), runner)
    lv_request = next(call for call in runner.calls if call.worker == "chords_lvchordia")
    assert lv_request.inputs["audio"].endswith("source.wav")


def test_stems_are_shared_between_runs_of_the_same_audio(track, tmp_path):
    analyze(request(track, tmp_path), FakeRunner(track))
    run_dir = run_dir_for(tmp_path / "runs", file_sha256(track.mix_path))
    (run_dir / "state.json").unlink()
    runner = FakeRunner(track)
    state = analyze(request(track, tmp_path), runner)
    assert "separate_bsroformer" not in runner.workers_called()
    assert state.record("separating").cached


def test_an_unsupported_upload_is_rejected_before_any_work(tmp_path):
    upload = tmp_path / "take.ogg"
    upload.write_bytes(b"x")
    with pytest.raises(PipelineError, match="MP3, WAV, FLAC or M4A"):
        analyze(AnalysisRequest(audio=upload, instruments=TRIO, out_root=tmp_path / "runs"), None)


def test_without_a_bass_stem_the_bass_check_is_skipped(track, tmp_path):
    state = analyze(
        request(track, tmp_path, instruments=(Instrument.PIANO, Instrument.DRUMS)),
        FakeRunner(track),
    )
    document = analysis_from_json(Path(state.record("decoded").outputs["analysis"]).read_text())
    assert {record.bass_pitch_class for record in document.chart} == {None}


def test_a_separator_that_drops_a_stem_fails_the_stage(track, tmp_path):
    stems = {name: s for name, s in track.stems.items() if name != "bass"}
    broken = type(track)(track.mix_path, stems, track.chords, track.beats, track.downbeats)
    with pytest.raises(PipelineError, match="separating failed: The separator wrote no 'bass'"):
        analyze(request(track, tmp_path), FakeRunner(broken))


def test_a_first_downbeat_past_the_end_fails_tracking(track, tmp_path):
    with pytest.raises(PipelineError, match="tracking failed: The first downbeat must be"):
        analyze(
            request(track, tmp_path, beats_per_bar=4, first_downbeat_index=99), FakeRunner(track)
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [({"beats_per_bar": 0}, "at least 1"), ({"chord_input": "stems"}, "no_drums or full_mix")],
)
def test_invalid_requests_are_rejected(track, tmp_path, fields, message):
    with pytest.raises(ValueError, match=message):
        request(track, tmp_path, **fields)


def test_each_finished_stage_is_reported(track, tmp_path):
    seen = []
    analyze(request(track, tmp_path), FakeRunner(track), on_stage=lambda r: seen.append(r.stage))
    assert seen == list(STAGES)


def test_a_tapped_tempo_builds_the_grid_without_the_tracker(track, tmp_path):
    analyze(request(track, tmp_path), FakeRunner(track))
    runner = FakeRunner(track)
    state = analyze(
        request(track, tmp_path, beats_per_bar=4, tempo_bpm=100.0, first_beat_time=0.25), runner
    )
    assert runner.workers_called() == []
    assert state.record("separating").cached and state.record("recognising").cached
    assert not state.record("tracking").cached and not state.record("decoded").cached
    grid = json.loads(Path(state.record("tracking").outputs["grid"]).read_text())
    assert [beat["time"] for beat in grid[:3]] == [0.25, 0.85, 1.45]
    assert grid[-1]["time"] < 8.0
    assert [(beat["bar"], beat["beat"]) for beat in grid[:5]] == [
        (1, 1), (1, 2), (1, 3), (1, 4), (2, 1),
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"tempo_bpm": 100.0}, "first_beat_time"),
        ({"first_beat_time": 0.5}, "tempo_bpm"),
        ({"tempo_bpm": 5.0, "first_beat_time": 0.0}, "20 to 400"),
        ({"tempo_bpm": 100.0, "first_beat_time": -1.0}, "not be negative"),
    ],
)
def test_invalid_tapped_tempos_are_rejected(track, tmp_path, fields, message):
    with pytest.raises(ValueError, match=message):
        request(track, tmp_path, **fields)
