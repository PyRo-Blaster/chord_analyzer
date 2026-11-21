"""Stage 4, recognising: both chord models on the same audio."""

import time
from collections.abc import Callable
from pathlib import Path

from jca_core.schema.records import ChordSegment

from jca_pipeline.adapters import ParsedChords, segments_from_btc, segments_from_lv_chordia
from jca_pipeline.config import BTC, LV_CHORDIA, ModelChoice
from jca_pipeline.contract import WorkerRequest, WorkerResult
from jca_pipeline.runner import WorkerRunner
from jca_pipeline.stages.common import metric_of, read_json, write_json
from jca_pipeline.state import StageRecord, WorkerMetric

MODELS: tuple[tuple[str, ModelChoice, Callable[[Path], ParsedChords]], ...] = (
    ("lv_chordia", LV_CHORDIA, segments_from_lv_chordia),
    ("btc", BTC, segments_from_btc),
)


def run_recognition(audio: Path, run_dir: Path, key: str, runner: WorkerRunner) -> StageRecord:
    started = time.monotonic()
    out = run_dir / "chords"
    runs = tuple(
        _run_model(name, choice, parse, audio, out, runner) for name, choice, parse in MODELS
    )
    return StageRecord(
        stage="recognising",
        key=key,
        outputs={name: str(path) for name, path, _, _ in runs},
        seconds=time.monotonic() - started,
        workers=tuple(metric for _, _, metric, _ in runs),
        warnings=tuple(warning for _, _, _, warnings in runs for warning in warnings),
    )


def load_segments(path: Path) -> tuple[ChordSegment, ...]:
    return tuple(ChordSegment.model_validate(segment) for segment in read_json(path))


def _run_model(
    name: str,
    choice: ModelChoice,
    parse: Callable[[Path], ParsedChords],
    audio: Path,
    out: Path,
    runner: WorkerRunner,
) -> tuple[str, Path, WorkerMetric, tuple[str, ...]]:
    worker_dir = out / name
    result: WorkerResult = runner.run(
        WorkerRequest(
            worker=choice.worker,
            inputs={"audio": str(audio)},
            params=choice.params,
            output_dir=str(worker_dir),
        )
    )
    parsed = parse(worker_dir / result.outputs["chords"])
    path = write_json(out / f"{name}.segments.json", [s.model_dump() for s in parsed.segments])
    return name, path, metric_of(result), parsed.warnings
