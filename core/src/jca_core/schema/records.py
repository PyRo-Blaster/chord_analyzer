"""Records that move between the pipeline stages, the API and the exports."""

from typing import Self

from pydantic import Field, model_validator

from jca_core.chords.agreement import Agreement
from jca_core.chords.parts import ChordParts
from jca_core.schema.base import FrozenModel

SCHEMA_VERSION = 1


class Beat(FrozenModel):
    """One beat of the grid. Bar 0 holds pickup beats before the first downbeat."""

    time: float = Field(ge=0)
    bar: int = Field(ge=0)
    beat: int = Field(ge=1)


class ChordSegment(FrozenModel):
    """One chord from a model: a Harte label over a time range in seconds."""

    start: float = Field(ge=0)
    end: float
    label: str = Field(min_length=1)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self


class ChartRecord(FrozenModel):
    """The chart record of the design, one for each beat."""

    bar: int = Field(ge=0)
    beat: int = Field(ge=1)
    time: float = Field(ge=0)
    lv_chordia: str
    btc: str
    bass_pitch_class: str | None
    agreement: Agreement
    draft: ChordParts
    confidence: float = Field(ge=0, le=1)
    extensions_confidence: float = Field(default=0.0, ge=0, le=1)
    needs_review: bool = False
    user_edit: ChordParts | None = None


class AnalysisDocument(FrozenModel):
    """Everything the JSON export holds: grid, both model outputs, chart with edits."""

    schema_version: int = SCHEMA_VERSION
    beats: tuple[Beat, ...]
    lv_chordia: tuple[ChordSegment, ...]
    btc: tuple[ChordSegment, ...]
    chart: tuple[ChartRecord, ...]
