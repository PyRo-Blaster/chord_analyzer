"""Stage 3, tracking: beats and bars from the full mix, or from the user's time signature."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf
from jca_core.grid.beats import build_beat_grid, regular_beat_grid
from jca_core.schema.records import Beat

from jca_pipeline.adapters import beats_from_tracker
from jca_pipeline.config import TRACKER
from jca_pipeline.contract import WorkerRequest
from jca_pipeline.runner import WorkerRunner
from jca_pipeline.stages.common import StageError, metric_of, read_json, write_json
from jca_pipeline.state import StageRecord

GRID_FILE = "grid.json"
DEFAULT_BEATS_PER_BAR = 4
SECONDS_PER_MINUTE = 60.0
MIN_TEMPO_BPM = 20.0
MAX_TEMPO_BPM = 400.0
TIME_DECIMALS = 6


@dataclass(frozen=True)
class GridSettings:
    """The user's corrections to the bar grid. All None means: trust the tracker."""

    beats_per_bar: int | None = None
    first_downbeat_index: int | None = None
    tempo_bpm: float | None = None  # a tapped tempo replaces the tracker
    first_beat_time: float | None = None

    def __post_init__(self) -> None:
        if self.first_downbeat_index is not None and self.beats_per_bar is None:
            raise ValueError("Set beats_per_bar to move the first downbeat")
        if self.beats_per_bar is not None and self.beats_per_bar < 1:
            raise ValueError(f"beats_per_bar must be at least 1, got {self.beats_per_bar}")
        if (self.tempo_bpm is None) != (self.first_beat_time is None):
            raise ValueError("A tapped tempo needs both tempo_bpm and first_beat_time")
        if self.tempo_bpm is not None and not MIN_TEMPO_BPM <= self.tempo_bpm <= MAX_TEMPO_BPM:
            raise ValueError(f"tempo_bpm must be from 20 to 400, got {self.tempo_bpm}")
        if self.first_beat_time is not None and self.first_beat_time < 0:
            raise ValueError("first_beat_time must not be negative")

    @property
    def tapped(self) -> bool:
        return self.tempo_bpm is not None


def run_tracking(
    source: Path, run_dir: Path, key: str, runner: WorkerRunner, settings: GridSettings
) -> StageRecord:
    started = time.monotonic()
    out = run_dir / "beats"
    if settings.tapped:
        grid = _tapped_grid(source, settings)
        grid_path = write_json(out / GRID_FILE, [beat.model_dump() for beat in grid])
        return StageRecord(
            stage="tracking",
            key=key,
            outputs={"grid": str(grid_path)},
            seconds=time.monotonic() - started,
        )
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
    grid = _grid(beats, downbeats, settings.beats_per_bar, settings.first_downbeat_index)
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


def _tapped_grid(source: Path, settings: GridSettings) -> tuple[Beat, ...]:
    duration = sf.info(source).duration
    step = SECONDS_PER_MINUTE / (settings.tempo_bpm or MIN_TEMPO_BPM)
    start = settings.first_beat_time or 0.0
    if start >= duration:
        raise StageError(f"The first tapped beat ({start:.2f} s) is after the end of the track")
    count = int((duration - start) / step) + 1
    beats = [round(start + index * step, TIME_DECIMALS) for index in range(count)]
    beats = [beat for beat in beats if beat < duration]
    index = settings.first_downbeat_index or 0
    if not 0 <= index < len(beats):
        raise StageError(
            f"The first downbeat must be a beat from 0 to {len(beats) - 1}, got {index}"
        )
    return regular_beat_grid(
        beats, settings.beats_per_bar or DEFAULT_BEATS_PER_BAR, first_downbeat_index=index
    )


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
