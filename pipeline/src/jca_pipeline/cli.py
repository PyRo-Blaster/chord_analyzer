"""jca-analyze: one command from an audio file to stems, beats, chords and a chart."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from jca_core.separation.plan import Instrument

from jca_pipeline.config import WORKER_TIMEOUT_SECONDS, WORKERS_DIR
from jca_pipeline.orchestrator import AnalysisRequest, PipelineError, analyze
from jca_pipeline.runner import SubprocessRunner, WorkerRunner
from jca_pipeline.state import RunState, StageRecord

DEFAULT_OUT = Path("runs")
BYTES_PER_GB = 1e9
_VALID = ", ".join(instrument.value for instrument in Instrument)


def parse_instruments(text: str) -> tuple[Instrument, ...]:
    names = [name.strip().lower() for name in text.split(",") if name.strip()]
    if not names:
        raise ValueError("Name at least one instrument")
    return tuple(_instrument(name) for name in names)


def parse_horn_counts(items: Sequence[str]) -> dict[Instrument, int]:
    counts: dict[Instrument, int] = {}
    for item in items:
        name, separator, number = item.partition("=")
        if not separator or not number.strip().isdigit():
            raise ValueError(f"Write a horn count as name=number, for example trumpet=2: {item!r}")
        counts = {**counts, _instrument(name.strip().lower()): int(number)}
    return counts


def format_stage(record: StageRecord) -> str:
    status = "cached" if record.cached else "ran"
    lines = [f"{record.stage:<13} {status:<6} {record.seconds:5.1f} s"]
    lines += [
        f"    {m.worker:<20} {m.seconds:5.1f} s  {m.peak_memory_bytes / BYTES_PER_GB:5.2f} GB  {m.device}"
        for m in record.workers
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, runner: WorkerRunner | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = AnalysisRequest(
            audio=Path(args.audio),
            instruments=parse_instruments(args.instruments),
            out_root=Path(args.out),
            horn_counts=parse_horn_counts(args.horn_count),
            other=tuple(args.other),
            beats_per_bar=args.beats_per_bar,
            first_downbeat_index=args.first_downbeat,
            chord_input=args.chord_input.replace("-", "_"),
            primary=args.primary,
        )
        if not request.audio.is_file():
            raise ValueError(f"{request.audio} was not found")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    active = runner or SubprocessRunner(WORKERS_DIR, WORKER_TIMEOUT_SECONDS)
    try:
        state = analyze(request, active, on_stage=lambda record: print(format_stage(record)))
    except PipelineError as error:
        print(f"Error: {error}", file=sys.stderr)
        if error.log_tail:
            print(f"Last lines of the worker log:\n{error.log_tail}", file=sys.stderr)
        return 1
    _print_summary(state)
    return 0


def _print_summary(state: RunState) -> None:
    for warning in (w for record in state.stages for w in record.warnings):
        print(f"Warning: {warning}")
    decoded = state.record("decoded")
    if decoded is None:
        return
    print()
    print(Path(decoded.outputs["chart"]).read_text(encoding="utf-8"), end="")
    print()
    print(f"Analysis: {decoded.outputs['analysis']}")
    print(f"Chart:    {decoded.outputs['chart']}")


def _instrument(name: str) -> Instrument:
    try:
        return Instrument(name)
    except ValueError as error:
        raise ValueError(f"Unknown instrument {name!r}. Choose from: {_VALID}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jca-analyze",
        description="Separate stems, track beats and draft a chord chart for a jazz recording.",
    )
    parser.add_argument("audio", help="MP3, WAV, FLAC or M4A file")
    parser.add_argument("--instruments", required=True, help=f"comma-separated list from: {_VALID}")
    parser.add_argument(
        "--horn-count", action="append", default=[], metavar="NAME=N",
        help="players of one horn type, for example trumpet=2",
    )  # fmt: skip
    parser.add_argument(
        "--other", action="append", default=[], help="an instrument not in the list"
    )
    parser.add_argument("--beats-per-bar", type=int, help="set the time signature")
    parser.add_argument("--first-downbeat", type=int, help="index of the beat that starts bar 1")
    parser.add_argument(
        "--chord-input", choices=("no-drums", "full-mix"), default="no-drums",
        help="audio for the chord models",
    )  # fmt: skip
    parser.add_argument("--primary", choices=("lv_chordia", "btc"), default="lv_chordia")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder for runs and the cache")
    return parser


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
