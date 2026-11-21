"""Stage 3, tracking: beats and bars from the full mix, or from the user's time signature."""

import time
from collections.abc import Sequence
from pathlib import Path

from jca_core.grid.beats import build_beat_grid, regular_beat_grid
from jca_core.schema.records import Beat

from jca_pipeline.adapters import beats_from_tracker
from jca_pipeline.config import TRACKER
from jca_pipeline.contract import WorkerRequest
from jca_pipeline.runner import WorkerRunner
from jca_pipeline.stages.common import StageError, metric_of, read_json, write_json
from jca_pipeline.state import StageRecord

GRID_FILE = "grid.json"


def run_tracking(
    source: Path,
    run_dir: Path,
    key: str,
    runner: WorkerRunner,
    beats_per_bar: int | None,
    first_downbeat_index: int | None,
) -> StageRecord:
    started = time.monotonic()
    out = run_dir / "beats"
    result = runner.run(
        WorkerRequest(
            worker=TRACKER.worker,
            inputs={"audio": str(source)},
            params=TRACKER.params,
            output_dir=str(out / "tracker"),
        )
    )
    raw = out / "tracker" / result.outputs["beats"]
    beats, downbeats = beats_from_tracker(raw)
    grid = _grid(beats, downbeats, beats_per_bar, first_downbeat_index)
    grid_path = write_json(out / GRID_FILE, [beat.model_dump() for beat in grid])
    return StageRecord(
        stage="tracking",
        key=key,
        outputs={"raw": str(raw), "grid": str(grid_path)},
        seconds=time.monotonic() - started,
        workers=(metric_of(result),),
    )


def load_grid(path: Path) -> tuple[Beat, ...]:
    return tuple(Beat.model_validate(beat) for beat in read_json(path))


def _grid(
    beats: Sequence[float],
    downbeats: Sequence[float],
    beats_per_bar: int | None,
    first_downbeat_index: int | None,
) -> tuple[Beat, ...]:
    if beats_per_bar is None:
        return build_beat_grid(beats, downbeats)
    index = first_downbeat_index
    if index is None:
        index = min(range(len(beats)), key=lambda i: abs(beats[i] - downbeats[0]))
    if not 0 <= index < len(beats):
        raise StageError(
            f"The first downbeat must be a beat from 0 to {len(beats) - 1}, got {index}"
        )
    return regular_beat_grid(beats, beats_per_bar, first_downbeat_index=index)
