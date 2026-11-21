"""Response bodies, the instrument catalogue and the form presets."""

from typing import Literal
from urllib.parse import quote

from jca_core.schema.base import FrozenModel
from jca_core.separation.plan import BRASS, WINDS, Instrument
from jca_pipeline.state import STAGES
from pydantic import Field

from jca_api.jobs import Job, JobStatus

StageState = Literal["waiting", "running", "done", "failed"]
TRIO = ["piano", "double bass", "drums"]


class Preset(FrozenModel):
    id: str
    label: str
    instruments: list[str]
    horn_counts: dict[str, int] = Field(default_factory=dict)


PRESETS = (
    Preset(id="piano-trio", label="Piano trio", instruments=TRIO),
    Preset(id="quartet-one-horn", label="Quartet with one horn", instruments=[*TRIO, "tenor sax"]),
    Preset(
        id="quintet-two-horns",
        label="Quintet with two horns",
        instruments=[*TRIO, "tenor sax", "trumpet"],
    ),
    Preset(
        id="big-band",
        label="Big band",
        instruments=[
            *TRIO,
            "guitar",
            "alto sax",
            "tenor sax",
            "baritone sax",
            "trumpet",
            "trombone",
        ],
        horn_counts={"alto sax": 2, "tenor sax": 2, "trumpet": 4, "trombone": 4},
    ),
)


class Catalogue(FrozenModel):
    instruments: list[str]
    horns: list[str]
    presets: tuple[Preset, ...]


def catalogue() -> Catalogue:
    horns = WINDS | BRASS
    return Catalogue(
        instruments=[instrument.value for instrument in Instrument],
        horns=[instrument.value for instrument in Instrument if instrument in horns],
        presets=PRESETS,
    )


class StageView(FrozenModel):
    name: str
    state: StageState


class StemView(FrozenModel):
    name: str
    kind: Literal["stem", "residue"]
    url: str


class TrackView(FrozenModel):
    id: str
    filename: str
    created_at: str
    status: JobStatus
    progress: float
    stages: tuple[StageView, ...]
    warnings: tuple[str, ...]
    error: str | None
    stems: tuple[StemView, ...]


def track_view(job: Job, stem_names: list[str]) -> TrackView:
    finished = set(job.finished_stages)
    current = next((stage for stage in STAGES if stage not in finished), None)
    active: StageState | None = {"running": "running", "failed": "failed"}.get(job.status)

    def state(stage: str) -> StageState:
        if stage in finished:
            return "done"
        if stage == current and active is not None:
            return active
        return "waiting"

    stems = tuple(
        StemView(
            name=name,
            kind="residue" if name == "residue" else "stem",
            url=f"/api/tracks/{job.id}/stems/{quote(name)}",
        )
        for name in stem_names
    )
    return TrackView(
        id=job.id,
        filename=job.filename,
        created_at=job.created_at,
        status=job.status,
        progress=round(len(finished & set(STAGES)) / len(STAGES), 2),
        stages=tuple(StageView(name=stage, state=state(stage)) for stage in STAGES),
        warnings=job.warnings,
        error=job.error,
        stems=stems,
    )
