"""Run state: what each stage produced, under which key, and what failed."""

import os
from pathlib import Path
from typing import Literal

from jca_core.schema.base import FrozenModel
from pydantic import Field, ValidationError

STAGES = ("uploaded", "separating", "tracking", "recognising", "decoded")
Stage = Literal["uploaded", "separating", "tracking", "recognising", "decoded"]


class StateError(ValueError):
    """The state file of a run cannot be read."""


class WorkerMetric(FrozenModel):
    worker: str
    seconds: float = Field(ge=0)
    peak_memory_bytes: int = Field(ge=0)
    device: str


class StageRecord(FrozenModel):
    stage: Stage
    key: str
    outputs: dict[str, str]
    seconds: float = Field(ge=0)
    workers: tuple[WorkerMetric, ...] = ()
    warnings: tuple[str, ...] = ()
    cached: bool = False


class StageFailure(FrozenModel):
    stage: Stage
    error: str
    log_tail: str = ""


class RunState(FrozenModel):
    track_sha256: str
    stages: tuple[StageRecord, ...] = ()
    failure: StageFailure | None = None

    def record(self, stage: Stage) -> StageRecord | None:
        return next((record for record in self.stages if record.stage == stage), None)


def with_record(state: RunState, record: StageRecord) -> RunState:
    """Return a new state with this stage's record replaced, in stage order."""
    others = tuple(existing for existing in state.stages if existing.stage != record.stage)
    ordered = tuple(sorted((*others, record), key=lambda item: STAGES.index(item.stage)))
    failure = state.failure
    if failure is not None and failure.stage == record.stage:
        failure = None
    return state.model_copy(update={"stages": ordered, "failure": failure})


def with_failure(state: RunState, failure: StageFailure) -> RunState:
    return state.model_copy(update={"failure": failure})


def reusable(state: RunState | None, stage: Stage, key: str) -> StageRecord | None:
    """Return the stage's record if it has this key and all its output files still exist."""
    record = state.record(stage) if state is not None else None
    if record is None or record.key != key:
        return None
    if not all(Path(path).exists() for path in record.outputs.values()):
        return None
    return record


def save_state(path: Path, state: RunState) -> Path:
    """Write the state file atomically, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_state(path: Path) -> RunState | None:
    if not path.is_file():
        return None
    try:
        return RunState.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise StateError(f"{path} is not a valid run state; delete it to start again") from error
