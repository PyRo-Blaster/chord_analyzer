"""The chord chart of a job: the view with edits applied, edit checks, evidence and exports."""

import json
import zipfile
from bisect import bisect_left
from pathlib import Path
from typing import Literal

from jca_core.chords.display import chord_symbol
from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import EXTENSION_NAMES
from jca_core.chords.parts import ChordParts, chord_parts
from jca_core.evidence.chroma import chroma_per_beat
from jca_core.export.json_export import analysis_from_json, analysis_to_json
from jca_core.export.text_chart import text_chart
from jca_core.grid.beats import beat_boundaries
from jca_core.pitch import pitch_class_number
from jca_core.schema.base import FrozenModel
from jca_core.schema.records import AnalysisDocument
from jca_pipeline.audio import read_audio
from jca_pipeline.stages.tracking import load_grid
from jca_pipeline.state import RunState, load_state

from jca_api.jobs import ChartEdit, Job
from jca_api.service import stems_of

EvidenceSource = Literal["mix", "piano", "bass"]
EVIDENCE_SOURCES: tuple[EvidenceSource, ...] = ("mix", "piano", "bass")
EDIT_MATCH_SECONDS = 0.06  # an edit belongs to the beat within this distance
STATE_FILE = "state.json"
EVIDENCE_DIR = "evidence"
EXPORTS_DIR = "exports"
_ALLOWED_EXTENSIONS = frozenset(EXTENSION_NAMES)


class ChartNotReady(LookupError):
    """The job has not drafted its chart yet."""


class InvalidRequest(ValueError):
    """An edit or a request about the chart cannot be carried out. Shown to the user."""


InvalidEdit = InvalidRequest


class LabelView(FrozenModel):
    label: str
    parts: ChordParts
    symbol: str
    tier1: str
    tier2: str


class PartsView(FrozenModel):
    parts: ChordParts
    symbol: str
    tier1: str
    tier2: str


class BeatView(FrozenModel):
    index: int
    bar: int
    beat: int
    time: float
    agreement: str
    needs_review: bool
    confidence: float
    extensions_confidence: float
    bass_pitch_class: str | None
    lv_chordia: LabelView
    btc: LabelView
    draft: PartsView
    user_edit: PartsView | None


class GridView(FrozenModel):
    beats_per_bar: int | None
    first_downbeat_index: int | None
    tempo_bpm: float | None
    first_beat_time: float | None


class ChordView(FrozenModel):
    beats: tuple[BeatView, ...]
    duration: float
    unplaced_edits: int
    grid: GridView


def parts_view(parts: ChordParts) -> PartsView:
    return PartsView(
        parts=parts, symbol=chord_symbol(parts), tier1=_tier1(parts), tier2=_tier2(parts)
    )


def chord_view(job: Job) -> ChordView:
    document, unplaced = _edited_document(job)
    beats = tuple(
        BeatView(
            index=index,
            bar=record.bar,
            beat=record.beat,
            time=record.time,
            agreement=record.agreement.value,
            needs_review=record.needs_review,
            confidence=record.confidence,
            extensions_confidence=record.extensions_confidence,
            bass_pitch_class=record.bass_pitch_class,
            lv_chordia=_label_view(record.lv_chordia),
            btc=_label_view(record.btc),
            draft=parts_view(record.draft),
            user_edit=None if record.user_edit is None else parts_view(record.user_edit),
        )
        for index, record in enumerate(document.chart)
    )
    options = job.options
    return ChordView(
        beats=beats,
        duration=beat_boundaries(document.beats)[-1] if document.beats else 0.0,
        unplaced_edits=unplaced,
        grid=GridView(
            beats_per_bar=options.beats_per_bar,
            first_downbeat_index=options.first_downbeat_index,
            tempo_bpm=options.tempo_bpm,
            first_beat_time=options.first_beat_time,
        ),
    )


def validate_edits(job: Job, edits: list[ChartEdit]) -> list[ChartEdit]:
    """Check each edit and move its time onto the exact beat time of the current chart."""
    times = [record.time for record in _document(job).chart]
    checked = []
    for edit in edits:
        beat_time = _nearest_beat(times, edit.time)
        if beat_time is None:
            raise InvalidRequest(f"There is no beat at {edit.time:.2f} s in this chart")
        if edit.user_edit is not None:
            _check_parts(edit.user_edit)
        checked.append(edit.model_copy(update={"time": beat_time}))
    return checked


def export_text(job: Job) -> str:
    return text_chart(_edited_document(job)[0].chart)


def export_json(job: Job) -> str:
    return analysis_to_json(_edited_document(job)[0])


def export_stems_zip(job: Job, target_dir: Path) -> Path:
    stems = stems_of(job)
    if not stems:
        raise ChartNotReady("The stems are not ready yet")
    prefix = Path(job.filename).stem
    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir / f"{job.id}-stems.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for path in stems.values():
            bundle.write(path, arcname=f"{prefix}-{path.name}")  # FLAC is compressed already
    return archive


def evidence(job: Job, source: EvidenceSource) -> tuple[tuple[float, ...], ...]:
    """A pitch-class profile for each beat, cached for each source and grid."""
    state = _state(job)
    tracking = state.record("tracking")
    separating = state.record("separating")
    if tracking is None or separating is None or job.run_dir is None:
        raise ChartNotReady("The beat grid is not ready yet")
    audio = _evidence_audio(job, source, separating.outputs)
    cache = (
        Path(job.run_dir)
        / EVIDENCE_DIR
        / f"{source}-{tracking.key[:16]}-{separating.key[:16]}.json"
    )
    if cache.is_file():
        return tuple(tuple(profile) for profile in json.loads(cache.read_text(encoding="utf-8")))
    samples, rate = read_audio(audio)
    profiles = chroma_per_beat(samples, rate, load_grid(Path(tracking.outputs["grid"])))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(profiles), encoding="utf-8")
    return profiles


def _evidence_audio(job: Job, source: EvidenceSource, outputs: dict[str, str]) -> Path:
    if source == "mix":
        return Path(outputs["no_drums"])
    if source == "bass":
        if "bass" not in outputs:
            raise InvalidRequest("This track has no bass stem")
        return Path(outputs["bass"])
    piano = stems_of(job).get("piano")
    if piano is None:
        raise InvalidRequest("This track has no piano stem")
    return piano


def _state(job: Job) -> RunState:
    state = load_state(Path(job.run_dir) / STATE_FILE) if job.run_dir else None
    if state is None:
        raise ChartNotReady("The chart is not ready yet")
    return state


def _document(job: Job) -> AnalysisDocument:
    record = _state(job).record("decoded")
    if record is None:
        raise ChartNotReady("The chart is not ready yet")
    return analysis_from_json(Path(record.outputs["analysis"]).read_text(encoding="utf-8"))


def _edited_document(job: Job) -> tuple[AnalysisDocument, int]:
    document = _document(job)
    times = [record.time for record in document.chart]
    by_time = {}
    unplaced = 0
    for edit in job.edits:
        beat_time = _nearest_beat(times, edit.time)
        if beat_time is None:
            unplaced += 1
        else:
            by_time[beat_time] = edit.user_edit
    chart = tuple(
        record.model_copy(update={"user_edit": by_time[record.time]})
        if record.time in by_time
        else record
        for record in document.chart
    )
    return document.model_copy(update={"chart": chart}), unplaced


def _nearest_beat(times: list[float], time: float) -> float | None:
    index = bisect_left(times, time)
    candidates = times[max(0, index - 1) : index + 1]
    nearest = min(candidates, key=lambda candidate: abs(candidate - time), default=None)
    if nearest is None or abs(nearest - time) > EDIT_MATCH_SECONDS:
        return None
    return nearest


def _check_parts(parts: ChordParts) -> None:
    if parts.root is None:
        if parts.chord_class is not None or parts.extensions or parts.bass is not None:
            raise InvalidRequest("A chord without a root must be no chord (N.C.)")
        return
    for role, name in (("root", parts.root), ("bass", parts.bass)):
        if name is None:
            continue
        try:
            pitch_class_number(name)
        except ValueError as error:
            raise InvalidRequest(f"The {role} {name!r} is not a note name") from error
    unknown = [name for name in parts.extensions if name not in _ALLOWED_EXTENSIONS]
    if unknown:
        raise InvalidRequest(f"The extension {unknown[0]!r} is not one the chart can show")


def _label_view(label: str) -> LabelView:
    parts = chord_parts(parse_chord(label))
    return LabelView(
        label=label,
        parts=parts,
        symbol=chord_symbol(parts),
        tier1=_tier1(parts),
        tier2=_tier2(parts),
    )


def _tier1(parts: ChordParts) -> str:
    if parts.root is None:
        return "N.C."
    if parts.chord_class is None:
        return chord_symbol(parts.model_copy(update={"bass": None}))
    return f"{parts.root} {parts.chord_class.value}"


def _tier2(parts: ChordParts) -> str:
    bass = [f"bass {parts.bass}"] if parts.bass and parts.bass != parts.root else []
    return ", ".join([*parts.extensions, *bass])
