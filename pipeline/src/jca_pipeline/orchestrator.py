"""Run the five stages in order, reuse what is still valid, and record failures."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from jca_core.cache.key import file_sha256, stem_cache_key
from jca_core.decoder.draft import PrimaryModel
from jca_core.separation.plan import Instrument, build_separation_plan, has_chordal_instrument

from jca_pipeline.audio import check_supported
from jca_pipeline.config import BTC, CAPABILITIES, LV_CHORDIA, SEPARATOR, TRACKER
from jca_pipeline.keys import decoding_key, recognition_key, tracking_key
from jca_pipeline.runner import WorkerFailed, WorkerRunner
from jca_pipeline.stages.decoding import run_decoding
from jca_pipeline.stages.ingest import run_ingest
from jca_pipeline.stages.recognition import run_recognition
from jca_pipeline.stages.separation import run_separation
from jca_pipeline.stages.tracking import run_tracking
from jca_pipeline.state import (
    RunState,
    Stage,
    StageFailure,
    StageRecord,
    load_state,
    reusable,
    save_state,
    with_failure,
    with_record,
)

ChordInput = Literal["no_drums", "full_mix"]
STATE_FILE = "state.json"
CACHE_DIR = "cache"
RUN_DIR_HASH_CHARS = 16


class PipelineError(RuntimeError):
    def __init__(self, stage: Stage, message: str, log_tail: str = "") -> None:
        super().__init__(f"{stage} failed: {message}")
        self.stage = stage
        self.log_tail = log_tail


@dataclass(frozen=True)
class AnalysisRequest:
    audio: Path
    instruments: tuple[Instrument, ...]
    out_root: Path
    horn_counts: Mapping[Instrument, int] = field(default_factory=dict)
    other: tuple[str, ...] = ()
    beats_per_bar: int | None = None
    first_downbeat_index: int | None = None
    chord_input: ChordInput = "no_drums"
    primary: PrimaryModel = "lv_chordia"

    def __post_init__(self) -> None:
        if self.first_downbeat_index is not None and self.beats_per_bar is None:
            raise ValueError("Set beats_per_bar to move the first downbeat")
        if self.beats_per_bar is not None and self.beats_per_bar < 1:
            raise ValueError(f"beats_per_bar must be at least 1, got {self.beats_per_bar}")
        if self.chord_input not in ("no_drums", "full_mix"):
            raise ValueError(f"chord_input must be no_drums or full_mix, got {self.chord_input}")


def run_dir_for(out_root: Path, audio_sha256: str) -> Path:
    return out_root / audio_sha256[:RUN_DIR_HASH_CHARS]


def analyze(
    request: AnalysisRequest,
    runner: WorkerRunner,
    on_stage: Callable[[StageRecord], None] | None = None,
) -> RunState:
    """Run or reuse each stage and return the final state. Raises PipelineError on failure."""
    try:
        check_supported(request.audio)
        sha = file_sha256(request.audio)
    except (ValueError, OSError) as error:
        raise PipelineError("uploaded", str(error)) from error
    run_dir = run_dir_for(request.out_root, sha)
    state_path = run_dir / STATE_FILE
    state = load_state(state_path) or RunState(track_sha256=sha)
    cache_dir = request.out_root / CACHE_DIR
    plan = build_separation_plan(
        request.instruments, CAPABILITIES, horn_counts=request.horn_counts, other=request.other
    )
    separation_key = stem_cache_key(
        sha, SEPARATOR.model, request.instruments, horn_counts=request.horn_counts,
        other=request.other,
    )  # fmt: skip
    keys: dict[Stage, str] = {
        "uploaded": sha,
        "separating": separation_key,
        "tracking": tracking_key(
            sha, TRACKER.model, request.beats_per_bar, request.first_downbeat_index
        ),
    }
    keys["recognising"] = recognition_key(
        separation_key, request.chord_input, {"lv": LV_CHORDIA.model, "btc": BTC.model}
    )
    keys["decoded"] = decoding_key(
        separation_key,
        keys["tracking"],
        keys["recognising"],
        request.primary,
        has_chordal_instrument(request.instruments),
    )

    def out(stage: Stage, name: str) -> Path:
        record = state.record(stage)
        assert record is not None  # earlier stages always run first
        return Path(record.outputs[name])

    def bass_stem() -> Path | None:
        record = state.record("separating")
        return Path(record.outputs["bass"]) if record and "bass" in record.outputs else None

    steps: tuple[tuple[Stage, Callable[[], StageRecord]], ...] = (
        ("uploaded", lambda: run_ingest(request.audio, run_dir, sha)),
        (
            "separating",
            lambda: run_separation(
                out("uploaded", "source"), plan, separation_key, cache_dir, runner
            ),
        ),
        (
            "tracking",
            lambda: run_tracking(
                out("uploaded", "source"),
                run_dir,
                keys["tracking"],
                runner,
                request.beats_per_bar,
                request.first_downbeat_index,
            ),
        ),
        (
            "recognising",
            lambda: run_recognition(
                out("separating", "no_drums")
                if request.chord_input == "no_drums"
                else out("uploaded", "source"),
                run_dir,
                keys["recognising"],
                runner,
            ),
        ),
        (
            "decoded",
            lambda: run_decoding(
                out("tracking", "grid"),
                out("recognising", "lv_chordia"),
                out("recognising", "btc"),
                bass_stem(),
                run_dir,
                keys["decoded"],
                request.primary,
                has_chordal_instrument(request.instruments),
            ),
        ),
    )
    for stage, step in steps:
        state = _run_step(state, state_path, stage, keys[stage], step)
        if on_stage is not None:
            on_stage(state.record(stage))
    return state


def _run_step(
    state: RunState, state_path: Path, stage: Stage, key: str, step: Callable[[], StageRecord]
) -> RunState:
    previous = reusable(state, stage, key)
    if previous is not None:
        updated = with_record(state, previous.model_copy(update={"cached": True}))
        save_state(state_path, updated)
        return updated
    try:
        record = step()
    except Exception as error:
        log_tail = error.log_tail if isinstance(error, WorkerFailed) else ""
        failure = StageFailure(stage=stage, error=str(error), log_tail=log_tail)
        save_state(state_path, with_failure(state, failure))
        raise PipelineError(stage, str(error), log_tail) from error
    updated = with_record(state, record)
    save_state(state_path, updated)
    return updated
