"""Queue uploads, run the analysis for one job at a time, and report what each job has."""

import logging
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from jca_core.cache.key import file_sha256
from jca_core.separation.plan import Instrument
from jca_pipeline.audio import AudioError, check_supported
from jca_pipeline.orchestrator import AnalysisRequest, PipelineError, analyze, run_dir_for
from jca_pipeline.runner import WorkerRunner
from jca_pipeline.state import RunState, StageRecord, load_state

from jca_api.jobs import Job, JobOptions, JobRepository

logger = logging.getLogger(__name__)

AnalyzeFn = Callable[[AnalysisRequest, Callable[[StageRecord], None]], RunState]
CHUNK_BYTES = 1024 * 1024
UPLOADS_DIR = "uploads"
RUNS_DIR = "runs"
DEFAULT_FILENAME = "upload"
STEM_PREFIX = "stem:"
RESIDUE = "residue"


class InvalidUpload(ValueError):
    """The upload or its options cannot be analysed. The message is shown to the user."""


def analyze_with(runner: WorkerRunner) -> AnalyzeFn:
    def analyze_fn(request: AnalysisRequest, on_stage: Callable[[StageRecord], None]) -> RunState:
        return analyze(request, runner, on_stage=on_stage)

    return analyze_fn


def stems_of(job: Job) -> dict[str, Path]:
    """The stems and the residue a job has so far, by name, in the order of the plan."""
    if job.run_dir is None:
        return {}
    state = load_state(Path(job.run_dir) / "state.json")
    record = state.record("separating") if state is not None else None
    if record is None:
        return {}
    stems = {
        key.removeprefix(STEM_PREFIX): Path(path)
        for key, path in record.outputs.items()
        if key.startswith(STEM_PREFIX)
    }
    return {**stems, RESIDUE: Path(record.outputs[RESIDUE])}


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        data_dir: Path,
        analyze_fn: AnalyzeFn,
        max_upload_bytes: int,
    ) -> None:
        self.repository = repository
        self._data_dir = data_dir
        self._analyze = analyze_fn
        self._max_upload_bytes = max_upload_bytes

    def submit(self, filename: str, stream: BinaryIO, options: JobOptions) -> Job:
        """Validate, save the upload in chunks, and queue a job."""
        name = Path(filename).name.strip() or DEFAULT_FILENAME
        try:
            check_supported(Path(name))
        except AudioError as error:
            raise InvalidUpload(str(error)) from error
        self._request(Path(name), options)  # validates the options before any write
        staging = self._data_dir / UPLOADS_DIR / f".incoming-{threading.get_ident()}"
        target = staging / name
        try:
            self._save(stream, target)
        except InvalidUpload:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        job = self.repository.create(filename=name, audio_path="", options=options)
        final_dir = self._data_dir / UPLOADS_DIR / job.id
        staging.rename(final_dir)
        audio_path = final_dir / name
        return self.repository.set_audio_path(job.id, str(audio_path))

    def run_next(self) -> Job | None:
        """Run the oldest queued job to the end. Returns it, or None if the queue is empty."""
        job = self.repository.next_queued()
        if job is None:
            return None
        try:
            audio = Path(job.audio_path)
            run_dir = run_dir_for(self._data_dir / RUNS_DIR, file_sha256(audio))
            self.repository.mark_running(job.id, run_dir=str(run_dir))
            warnings: list[str] = []

            def on_stage(record: StageRecord) -> None:
                warnings.extend(w for w in record.warnings if w not in warnings)
                self.repository.add_finished_stage(job.id, record.stage)

            self._analyze(self._request(audio, job.options), on_stage)
        except (PipelineError, InvalidUpload) as error:
            return self.repository.mark_failed(job.id, str(error))
        except Exception as error:
            logger.exception("Job %s failed", job.id)
            return self.repository.mark_failed(job.id, f"Unexpected error: {error}")
        return self.repository.mark_done(job.id, warnings=warnings)

    def _request(self, audio: Path, options: JobOptions) -> AnalysisRequest:
        low = sorted(name for name, count in options.horn_counts.items() if count < 1)
        if low:
            raise InvalidUpload(f"Horn counts must be at least 1: {', '.join(low)}")
        try:
            return AnalysisRequest(
                audio=audio,
                instruments=tuple(_instrument(name) for name in options.instruments),
                out_root=self._data_dir / RUNS_DIR,
                horn_counts={_instrument(k): v for k, v in options.horn_counts.items()},
                other=tuple(options.other),
                beats_per_bar=options.beats_per_bar,
                first_downbeat_index=options.first_downbeat_index,
                tempo_bpm=options.tempo_bpm,
                first_beat_time=options.first_beat_time,
            )
        except ValueError as error:
            raise InvalidUpload(str(error)) from error

    def _save(self, stream: BinaryIO, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with target.open("wb") as handle:
            while chunk := stream.read(CHUNK_BYTES):
                written += len(chunk)
                if written > self._max_upload_bytes:
                    limit = self._max_upload_bytes // (1024 * 1024)
                    raise InvalidUpload(f"The file is larger than the {limit} MB limit")
                handle.write(chunk)


def _instrument(name: str) -> Instrument:
    try:
        instrument = Instrument(name.strip().lower())
    except ValueError as error:
        raise ValueError(f"Unknown instrument {name!r}") from error
    return instrument


class JobWorker:
    """One background thread that runs queued jobs one after another."""

    def __init__(self, service: JobService, poll_seconds: float = 1.0) -> None:
        self._service = service
        self._poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="jca-job-worker", daemon=True)

    def start(self) -> None:
        requeued = self._service.repository.requeue_running()
        if requeued:
            logger.warning("Put %d interrupted job(s) back in the queue", requeued)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._service.run_next() is None:
                self._stop.wait(self._poll_seconds)
