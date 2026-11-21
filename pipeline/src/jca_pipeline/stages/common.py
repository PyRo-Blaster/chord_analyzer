"""Small helpers shared by the stages."""

import json
from pathlib import Path
from typing import Any

from jca_pipeline.contract import WorkerResult
from jca_pipeline.state import WorkerMetric


class StageError(ValueError):
    """A stage cannot go on with what earlier stages produced."""


def metric_of(result: WorkerResult) -> WorkerMetric:
    return WorkerMetric(
        worker=result.worker,
        seconds=result.seconds,
        peak_memory_bytes=result.peak_memory_bytes,
        device=result.device,
    )


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_slug(name: str) -> str:
    """A file name for a stem name such as "double bass"."""
    return name.replace(" ", "_")
