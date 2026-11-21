"""Parse the raw output of each model into core types.

Workers write raw model output unchanged, so all format knowledge lives here and is
tested against recorded outputs without running a model.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jca_core.chords.harte import InvalidChordLabelError, parse_chord
from jca_core.schema.base import FrozenModel
from jca_core.schema.records import ChordSegment
from pydantic import BaseModel, ConfigDict, Field, ValidationError

UNKNOWN_LABEL = "X"
INVALID_LABEL_WARNING = "{model} label {label!r} is not valid Harte notation; read as X"


class AdapterError(ValueError):
    """A worker output file is missing or not in the expected format."""


class ParsedChords(FrozenModel):
    segments: tuple[ChordSegment, ...]
    warnings: tuple[str, ...] = ()


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class _LvRow(_Raw):
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)
    chord: str


class _BtcRow(_Raw):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    chord: str


class _Beats(_Raw):
    beats: list[float] = Field(min_length=1)
    downbeats: list[float]


def segments_from_lv_chordia(path: Path) -> ParsedChords:
    """Read lv-chordia output: a list of {"start_time", "end_time", "chord"}."""
    rows = _validated_list(path, _LvRow)
    return _to_segments("lv-chordia", [(r.start_time, r.end_time, r.chord) for r in rows], path)


def segments_from_btc(path: Path) -> ParsedChords:
    """Read BTC output: a list of {"start", "end", "chord"}."""
    rows = _validated_list(path, _BtcRow)
    return _to_segments("BTC", [(r.start, r.end, r.chord) for r in rows], path)


def beats_from_tracker(path: Path) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Read tracker output {"beats": [...], "downbeats": [...]}: sorted, without repeats."""
    try:
        raw = _Beats.model_validate(_load(path))
    except ValidationError as error:
        raise AdapterError(
            f"{path.name}: not a beat tracker output ({error.error_count()} problem(s))"
        ) from error
    beats = tuple(sorted(set(raw.beats)))
    downbeats = tuple(sorted(set(raw.downbeats)))
    if beats[0] < 0 or (downbeats and downbeats[0] < 0):
        raise AdapterError(f"{path.name}: beat times must not be negative")
    if not downbeats:
        raise AdapterError(f"{path.name}: the tracker found no downbeat")
    return beats, downbeats


def _load(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise AdapterError(f"{path.name}: output file is missing") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise AdapterError(f"{path.name}: not valid JSON") from error


def _validated_list[T: BaseModel](path: Path, row_type: type[T]) -> list[T]:
    data = _load(path)
    if not isinstance(data, list):
        raise AdapterError(f"{path.name}: expected a list of chord segments")
    try:
        return [row_type.model_validate(row) for row in data]
    except ValidationError as error:
        raise AdapterError(
            f"{path.name}: unexpected segment format ({error.error_count()} problem(s))"
        ) from error


def _to_segments(model: str, rows: Sequence[tuple[float, float, str]], path: Path) -> ParsedChords:
    if any(end < start for start, end, _ in rows):
        raise AdapterError(f"{path.name}: a segment ends before it starts")
    invalid = tuple(dict.fromkeys(label for _, _, label in rows if not _is_valid(label)))
    segments = tuple(
        ChordSegment(start=start, end=end, label=UNKNOWN_LABEL if label in invalid else label)
        for start, end, label in sorted(rows)
        if end > start
    )
    warnings = tuple(INVALID_LABEL_WARNING.format(model=model, label=label) for label in invalid)
    return ParsedChords(segments=segments, warnings=warnings)


def _is_valid(label: str) -> bool:
    try:
        parse_chord(label)
    except InvalidChordLabelError:
        return False
    return True
