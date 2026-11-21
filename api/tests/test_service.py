import io
import shutil
import time

import numpy as np
import pytest
import soundfile as sf
from jca_pipeline.orchestrator import PipelineError
from jca_pipeline.state import RunState, StageRecord

from jca_api.fake_runner import FakeModelRunner
from jca_api.jobs import JobOptions, JobRepository
from jca_api.service import (
    InvalidUpload,
    JobService,
    JobWorker,
    analyze_with,
    stems_of,
)

TRIO = JobOptions(instruments=["piano", "double bass", "drums"])
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def wav_bytes(seconds: float = 4.0, rate: int = 44100) -> bytes:
    time_axis = np.arange(int(seconds * rate)) / rate
    tone = 0.2 * np.sin(2 * np.pi * 220 * time_axis)
    buffer = io.BytesIO()
    sf.write(buffer, np.column_stack([tone, tone]), rate, format="WAV")
    return buffer.getvalue()


def make_service(tmp_path, analyze_fn, max_upload_bytes=10_000_000) -> JobService:
    repository = JobRepository(tmp_path / "jobs.sqlite3")
    return JobService(repository, tmp_path / "data", analyze_fn, max_upload_bytes)


def recording_analyze(calls):
    def analyze_fn(request, on_stage):
        calls.append(request)
        for stage in ("uploaded", "separating"):
            on_stage(StageRecord(stage=stage, key="k", outputs={}, seconds=0.1, warnings=("w",)))
        return RunState(track_sha256="a" * 64)

    return analyze_fn


def test_submit_saves_the_upload_and_queues_a_job(tmp_path):
    service = make_service(tmp_path, recording_analyze([]))
    job = service.submit("../../take.wav", io.BytesIO(b"RIFF data"), TRIO)
    assert job.status == "queued"
    assert job.filename == "take.wav"
    saved = tmp_path / "data" / "uploads" / job.id / "take.wav"
    assert saved.read_bytes() == b"RIFF data"
    assert job.audio_path == str(saved)


@pytest.mark.parametrize(
    ("filename", "options", "message"),
    [
        ("take.ogg", TRIO, "MP3, WAV, FLAC or M4A"),
        ("take.wav", JobOptions(instruments=["banjo"]), "Unknown instrument 'banjo'"),
        ("take.wav", JobOptions(instruments=["piano"], horn_counts={"banjo": 2}), "banjo"),
        ("take.wav", JobOptions(instruments=["piano"], horn_counts={"trumpet": 0}), "at least 1"),
        ("take.wav", JobOptions(instruments=["piano"], first_downbeat_index=2), "beats_per_bar"),
    ],
)
def test_invalid_submissions_are_rejected_before_anything_is_saved(
    tmp_path, filename, options, message
):
    service = make_service(tmp_path, recording_analyze([]))
    with pytest.raises(InvalidUpload, match=message):
        service.submit(filename, io.BytesIO(b"x"), options)
    assert service.repository.recent() == ()


def test_an_upload_over_the_limit_is_rejected_and_removed(tmp_path):
    service = make_service(tmp_path, recording_analyze([]), max_upload_bytes=10)
    with pytest.raises(InvalidUpload, match="larger than"):
        service.submit("take.wav", io.BytesIO(b"x" * 11), TRIO)
    assert not list((tmp_path / "data" / "uploads").rglob("*.wav"))
    assert service.repository.recent() == ()


def test_run_next_runs_the_oldest_job_and_records_each_stage(tmp_path):
    calls = []
    service = make_service(tmp_path, recording_analyze(calls))
    job = service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    done = service.run_next()
    assert done.id == job.id
    assert done.status == "done"
    assert done.finished_stages == ("uploaded", "separating")
    assert done.warnings == ("w",)
    assert done.run_dir.startswith(str(tmp_path / "data" / "runs"))
    request = calls[0]
    assert [i.value for i in request.instruments] == ["piano", "double bass", "drums"]
    assert service.run_next() is None


def test_a_failed_analysis_marks_the_job_failed(tmp_path):
    def failing(request, on_stage):
        raise PipelineError("tracking", "beats_beatthis: model exploded")

    service = make_service(tmp_path, failing)
    service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    failed = service.run_next()
    assert failed.status == "failed"
    assert failed.error == "tracking failed: beats_beatthis: model exploded"


def test_an_unexpected_error_also_marks_the_job_failed(tmp_path):
    def broken(request, on_stage):
        raise RuntimeError("disk full")

    service = make_service(tmp_path, broken)
    service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    assert service.run_next().error == "Unexpected error: disk full"


@needs_ffmpeg
def test_the_real_orchestrator_with_fake_models_lists_the_stems(tmp_path):
    service = make_service(tmp_path, analyze_with(FakeModelRunner(delay_seconds=0)))
    service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    done = service.run_next()
    assert done.status == "done"
    assert done.finished_stages == (
        "uploaded", "separating", "tracking", "recognising", "decoded",
    )  # fmt: skip
    stems = stems_of(done)
    assert list(stems) == ["drums", "double bass", "piano", "residue"]
    assert all(path.is_file() for path in stems.values())


def test_stems_of_a_job_that_has_not_separated_yet_is_empty(tmp_path):
    service = make_service(tmp_path, recording_analyze([]))
    job = service.submit("take.wav", io.BytesIO(b"x"), TRIO)
    assert stems_of(job) == {}


def test_the_worker_thread_runs_queued_jobs(tmp_path):
    calls = []
    service = make_service(tmp_path, recording_analyze(calls))
    worker = JobWorker(service, poll_seconds=0.05)
    worker.start()
    try:
        job = service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
        deadline = time.monotonic() + 5
        while service.repository.get(job.id).status != "done" and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        worker.stop()
    assert service.repository.get(job.id).status == "done"
    assert not worker.is_alive()


def test_the_worker_requeues_jobs_left_running_by_a_crash(tmp_path):
    service = make_service(tmp_path, recording_analyze([]))
    job = service.submit("take.wav", io.BytesIO(wav_bytes()), TRIO)
    service.repository.mark_running(job.id, run_dir="/gone")
    worker = JobWorker(service, poll_seconds=0.05)
    worker.start()
    worker.stop()
    assert service.repository.get(job.id).status in ("queued", "done")
