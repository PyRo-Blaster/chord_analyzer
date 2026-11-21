"""Smoke tests on the real models. Run with: uv run --directory pipeline pytest -m model

They check shape and sanity only, never accuracy (accuracy is the Phase 2 evaluation).
Each test runs a worker in its own uv environment, so the environments and model
checkpoints must already be installed (see docs/phase0-results.md).
"""

from itertools import pairwise
from statistics import median

import pytest
import soundfile as sf
from jca_core.chords.harte import parse_chord

from jca_pipeline.adapters import beats_from_tracker, segments_from_btc, segments_from_lv_chordia
from jca_pipeline.config import BTC, LV_CHORDIA, SEPARATOR, TRACKER, WORKERS_DIR
from jca_pipeline.contract import WorkerRequest
from jca_pipeline.runner import SubprocessRunner

from ..synth import make_chord_clip, make_click_track, make_track

pytestmark = pytest.mark.model
RUNNER = SubprocessRunner(WORKERS_DIR, timeout_seconds=1800)
C = 0


def run(choice, inputs, out):
    request = WorkerRequest(
        worker=choice.worker, inputs=inputs, params=choice.params, output_dir=str(out)
    )
    return RUNNER.run(request)


def test_separator_keeps_the_rate_and_length_of_the_source(tmp_path):
    track = make_track(tmp_path / "audio")
    result = run(SEPARATOR, {"mix": str(track.mix_path)}, tmp_path / "out")
    assert set(result.outputs) == {"vocals", "drums", "bass", "guitar", "piano", "other"}
    source = sf.info(track.mix_path)
    for name in result.outputs.values():
        stem = sf.info(tmp_path / "out" / name)
        assert (stem.samplerate, stem.frames) == (source.samplerate, source.frames)


def test_beat_tracker_finds_120_bpm_on_a_groove(tmp_path):
    clicks = make_click_track(tmp_path / "audio")
    result = run(TRACKER, {"audio": str(clicks)}, tmp_path / "out")
    beats, downbeats = beats_from_tracker(tmp_path / "out" / result.outputs["beats"])
    gaps = [later - earlier for earlier, later in pairwise(beats)]
    assert 60 / median(gaps) == pytest.approx(120, abs=3)
    assert downbeats


@pytest.mark.parametrize(
    ("choice", "parse"), [(LV_CHORDIA, segments_from_lv_chordia), (BTC, segments_from_btc)]
)
def test_chord_model_reports_root_c_on_a_c_major_chord(tmp_path, choice, parse):
    clip = make_chord_clip(tmp_path / "audio")
    result = run(choice, {"audio": str(clip)}, tmp_path / "out")
    parsed = parse(tmp_path / "out" / result.outputs["chords"])
    longest = max(parsed.segments, key=lambda segment: segment.end - segment.start)
    assert parse_chord(longest.label).root_pc == C
    assert result.peak_memory_bytes > 0
