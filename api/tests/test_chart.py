import io
import json
import shutil
import zipfile

import numpy as np
import pytest
import soundfile as sf
from jca_core.chords.parts import ChordParts

from jca_api.chart import (
    ChartNotReady,
    InvalidEdit,
    InvalidRequest,
    chord_view,
    evidence,
    export_json,
    export_stems_zip,
    export_text,
    parts_view,
    validate_edits,
)
from jca_api.fake_runner import FakeModelRunner
from jca_api.jobs import ChartEdit, JobOptions, JobRepository
from jca_api.service import JobService, analyze_with

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
TRIO = JobOptions(instruments=["piano", "double bass", "drums"])
D_MINOR_7 = ChordParts.model_validate(
    {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"}
)


def wav_bytes(seconds: float = 8.0, rate: int = 44100) -> bytes:
    time = np.arange(int(seconds * rate)) / rate
    tone = 0.2 * np.sin(2 * np.pi * 261.63 * time) + 0.2 * np.sin(2 * np.pi * 65.41 * time)
    buffer = io.BytesIO()
    sf.write(buffer, np.column_stack([tone, tone]), rate, format="WAV")
    return buffer.getvalue()


@pytest.fixture
def service(tmp_path):
    return JobService(
        JobRepository(tmp_path / "jobs.sqlite3"),
        tmp_path / "data",
        analyze_with(FakeModelRunner(delay_seconds=0)),
        10_000_000,
    )


@pytest.fixture
def job(service):
    service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    return service.run_next()


def test_the_view_has_one_beat_with_both_models_and_the_draft(job):
    view = chord_view(job)
    assert len(view.beats) == 16
    first = view.beats[0]
    assert (first.index, first.bar, first.beat, first.time) == (0, 1, 1, 0.0)
    assert (first.lv_chordia.label, first.lv_chordia.symbol) == ("C:maj7", "Cmaj7")
    assert (first.btc.label, first.btc.symbol) == ("C:maj", "C")
    assert first.btc.parts.model_dump(mode="json") == {
        "root": "C", "class": "maj", "extensions": [], "bass": "C",
    }  # fmt: skip
    assert first.agreement == "B"
    assert (first.draft.tier1, first.draft.tier2, first.draft.symbol) == ("C maj", "7", "Cmaj7")
    assert first.user_edit is None
    assert view.beats[4].agreement == "D"
    assert view.beats[4].needs_review is True
    assert view.unplaced_edits == 0
    assert view.duration == pytest.approx(8.0)


def test_tiers_show_the_class_first_and_the_extensions_and_bass_second():
    view = parts_view(
        ChordParts.model_validate({"root": "G", "class": "dom7", "extensions": ["b9"], "bass": "B"})
    )
    assert (view.tier1, view.tier2, view.symbol) == ("G dom7", "b9, bass B", "G7b9/B")
    no_chord = parts_view(ChordParts(root=None, chord_class=None))
    assert (no_chord.tier1, no_chord.tier2, no_chord.symbol) == ("N.C.", "", "N.C.")
    sus = parts_view(
        ChordParts.model_validate({"root": "C", "class": None, "extensions": ["4", "5"]})
    )
    assert (sus.tier1, sus.tier2) == ("Csus4", "4, 5")


def test_edits_are_applied_and_kept_next_to_the_model_outputs(service, job):
    edits = validate_edits(job, [ChartEdit(time=2.0, user_edit=D_MINOR_7)])
    edited = service.repository.save_edits(job.id, edits)
    beat = chord_view(edited).beats[4]
    assert beat.user_edit.symbol == "Dm7"
    assert beat.draft.symbol == "Cmaj7"
    assert beat.lv_chordia.label == "C:maj7" and beat.btc.label == "A:min7"


def test_an_edit_time_is_snapped_to_its_beat(job):
    assert validate_edits(job, [ChartEdit(time=2.03, user_edit=D_MINOR_7)])[0].time == 2.0


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (ChartEdit(time=2.3, user_edit=D_MINOR_7), "no beat at 2.30 s"),
        (ChartEdit(time=0.0, user_edit=ChordParts(root="H", chord_class=None)), "root 'H'"),
        (
            ChartEdit(
                time=0.0,
                user_edit=ChordParts.model_validate({"root": "C", "class": "maj", "bass": "X#"}),
            ),
            "bass 'X#'",
        ),
        (
            ChartEdit(
                time=0.0,
                user_edit=ChordParts.model_validate(
                    {"root": "C", "class": "maj", "extensions": ["b15"]}
                ),
            ),
            "extension 'b15'",
        ),
        (
            ChartEdit(
                time=0.0, user_edit=ChordParts.model_validate({"root": None, "class": "maj"})
            ),
            "without a root",
        ),
    ],
)
def test_invalid_edits_are_rejected(job, edit, message):
    with pytest.raises(InvalidEdit, match=message):
        validate_edits(job, [edit])


def test_edits_that_no_longer_match_a_beat_are_counted_not_lost(service, job):
    edited = service.repository.save_edits(job.id, [ChartEdit(time=2.25, user_edit=D_MINOR_7)])
    view = chord_view(edited)
    assert view.unplaced_edits == 1
    assert all(beat.user_edit is None for beat in view.beats)
    assert len(edited.edits) == 1


def test_text_export_uses_the_edits(service, job):
    edited = service.repository.save_edits(
        job.id, [ChartEdit(time=t, user_edit=D_MINOR_7) for t in (2.0, 2.5, 3.0, 3.5)]
    )
    assert export_text(edited) == "| Cmaj7 | Dm7   | Cmaj7 | Cmaj7 |\n"


def test_json_export_holds_both_models_and_the_edits(service, job):
    edited = service.repository.save_edits(job.id, [ChartEdit(time=2.0, user_edit=D_MINOR_7)])
    document = json.loads(export_json(edited))
    assert document["lv_chordia"][0]["label"] == "C:maj7"
    assert document["chart"][4]["user_edit"]["root"] == "D"
    assert document["chart"][4]["draft"]["root"] == "C"


def test_stems_export_is_a_zip_of_the_flac_stems(job, tmp_path):
    archive = export_stems_zip(job, tmp_path / "exports")
    with zipfile.ZipFile(archive) as opened:
        assert sorted(opened.namelist()) == [
            "take-double_bass.flac", "take-drums.flac", "take-piano.flac", "take-residue.flac",
        ]  # fmt: skip


def test_evidence_has_twelve_values_for_each_beat_and_is_cached(job):
    profiles = evidence(job, "mix")
    assert len(profiles) == 16
    assert all(len(profile) == 12 for profile in profiles)
    assert max(profiles[0]) == pytest.approx(1.0)
    assert int(np.argmax(profiles[0])) == 0  # the test tone is a C
    assert evidence(job, "mix") == profiles
    assert len(evidence(job, "bass")) == 16


def test_evidence_for_a_missing_stem_is_refused(service):
    service.submit("take.wav", io.BytesIO(wav_bytes()), JobOptions(instruments=["drums"]))
    done = service.run_next()
    with pytest.raises(InvalidRequest, match="no piano stem"):
        evidence(done, "piano")


def test_a_job_without_a_chart_is_not_ready(service):
    queued = service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    with pytest.raises(ChartNotReady):
        chord_view(queued)
