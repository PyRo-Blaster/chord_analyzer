"""The job table: one row for each uploaded track, in SQLite."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from jca_core.chords.parts import ChordParts
from jca_core.schema.base import FrozenModel
from pydantic import Field

JobStatus = Literal["queued", "running", "done", "failed"]
DEFAULT_LIST_LIMIT = 50
BUSY_TIMEOUT_SECONDS = 10.0
SAME_BEAT_SECONDS = 0.001  # two edits within this time are for the same beat
STAGES_BEFORE_TRACKING = ("uploaded", "separating")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    filename TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    options TEXT NOT NULL,
    status TEXT NOT NULL,
    finished_stages TEXT NOT NULL DEFAULT '[]',
    run_dir TEXT,
    error TEXT,
    warnings TEXT NOT NULL DEFAULT '[]',
    edits TEXT NOT NULL DEFAULT '[]'
)
"""
# Columns added after the first release, with their definitions, for older tables.
_ADDED_COLUMNS = {"edits": "TEXT NOT NULL DEFAULT '[]'"}


class JobNotFound(KeyError):
    """No job has this id."""


class JobOptions(FrozenModel):
    """What the user chose in the upload form."""

    instruments: list[str] = Field(min_length=1)
    horn_counts: dict[str, int] = Field(default_factory=dict)
    other: list[str] = Field(default_factory=list)
    beats_per_bar: int | None = Field(default=None, ge=1, le=16)
    first_downbeat_index: int | None = Field(default=None, ge=0)
    tempo_bpm: float | None = Field(default=None, ge=20, le=400)
    first_beat_time: float | None = Field(default=None, ge=0)


class ChartEdit(FrozenModel):
    """The user's label for the beat at `time`. None clears an earlier edit."""

    time: float = Field(ge=0)
    user_edit: ChordParts | None


class Job(FrozenModel):
    id: str
    created_at: str
    filename: str
    audio_path: str
    options: JobOptions
    status: JobStatus
    finished_stages: tuple[str, ...] = ()
    run_dir: str | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()
    edits: tuple[ChartEdit, ...] = ()


class JobRepository:
    """Every call opens its own connection, so the API and the worker thread can share it."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(_SCHEMA)
            present = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)")}
            for name, definition in _ADDED_COLUMNS.items():
                if name not in present:
                    connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")

    def create(self, *, filename: str, audio_path: str, options: JobOptions) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            created_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
            filename=filename,
            audio_path=audio_path,
            options=options,
            status="queued",
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs (id, created_at, filename, audio_path, options, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job.id, job.created_at, filename, audio_path, options.model_dump_json(), "queued"),
            )
        return job

    def get(self, job_id: str) -> Job:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound(f"There is no track with id {job_id!r}")
        return _job(row)

    def recent(self, limit: int = DEFAULT_LIST_LIMIT) -> tuple[Job, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(_job(row) for row in rows)

    def next_queued(self) -> Job | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at, rowid LIMIT 1"
            ).fetchone()
        return None if row is None else _job(row)

    def set_audio_path(self, job_id: str, audio_path: str) -> Job:
        return self._update(job_id, audio_path=audio_path)

    def mark_running(self, job_id: str, *, run_dir: str) -> Job:
        return self._update(job_id, status="running", run_dir=run_dir, error=None)

    def add_finished_stage(self, job_id: str, stage: str) -> Job:
        stages = self.get(job_id).finished_stages
        if stage in stages:
            return self.get(job_id)
        return self._update(job_id, finished_stages=json.dumps([*stages, stage]))

    def mark_done(self, job_id: str, *, warnings: list[str]) -> Job:
        return self._update(job_id, status="done", warnings=json.dumps(warnings))

    def mark_failed(self, job_id: str, error: str) -> Job:
        return self._update(job_id, status="failed", error=error)

    def save_edits(self, job_id: str, edits: list[ChartEdit]) -> Job:
        """Merge edits by beat time: a new edit replaces one at the same time; None removes it."""
        kept = list(self.get(job_id).edits)
        for edit in edits:
            kept = [old for old in kept if abs(old.time - edit.time) > SAME_BEAT_SECONDS]
            if edit.user_edit is not None:
                kept.append(edit)
        ordered = sorted(kept, key=lambda edit: edit.time)
        payload = json.dumps([edit.model_dump(mode="json") for edit in ordered])
        return self._update(job_id, edits=payload)

    def requeue_with_options(self, job_id: str, options: JobOptions) -> Job:
        """Queue the job again with new options, keeping the stages a grid change does not touch."""
        kept = [s for s in self.get(job_id).finished_stages if s in STAGES_BEFORE_TRACKING]
        return self._update(
            job_id,
            status="queued",
            options=options.model_dump_json(),
            finished_stages=json.dumps(kept),
            error=None,
        )

    def requeue_running(self) -> int:
        """Put back jobs that were running when the server stopped. Returns how many."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status = 'queued' WHERE status = 'running'"
            )
            return cursor.rowcount

    def _update(self, job_id: str, **columns: object) -> Job:
        assignments = ", ".join(f"{name} = ?" for name in columns)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",  # names are fixed by the callers
                (*columns.values(), job_id),
            )
        if cursor.rowcount == 0:
            raise JobNotFound(f"There is no track with id {job_id!r}")
        return self.get(job_id)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def _job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        created_at=row["created_at"],
        filename=row["filename"],
        audio_path=row["audio_path"],
        options=JobOptions.model_validate_json(row["options"]),
        status=row["status"],
        finished_stages=tuple(json.loads(row["finished_stages"])),
        run_dir=row["run_dir"],
        error=row["error"],
        warnings=tuple(json.loads(row["warnings"])),
        edits=tuple(ChartEdit.model_validate(edit) for edit in json.loads(row["edits"])),
    )
