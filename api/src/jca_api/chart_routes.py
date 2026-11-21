"""Routes for the chord chart: the view, edits, the grid, evidence and exports."""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from jca_core.schema.base import FrozenModel
from jca_pipeline.stages.tracking import GridSettings
from pydantic import Field

from jca_api.chart import (
    EVIDENCE_SOURCES,
    EXPORTS_DIR,
    ChartNotReady,
    EvidenceSource,
    InvalidRequest,
    chord_view,
    evidence,
    export_json,
    export_stems_zip,
    export_text,
    validate_edits,
)
from jca_api.jobs import ChartEdit
from jca_api.schemas import track_view
from jca_api.service import JobService, stems_of

API_PREFIX = "/api"
MAX_EDITS_PER_REQUEST = 4000
ExportFormat = Literal["text", "json", "stems"]
EXPORT_FORMATS = ("text", "json", "stems")
BUSY_STATUSES = frozenset({"queued", "running"})


class ChartPatch(FrozenModel):
    edits: list[ChartEdit] = Field(min_length=1, max_length=MAX_EDITS_PER_REQUEST)


class GridPatch(FrozenModel):
    beats_per_bar: int | None = Field(default=None, ge=1, le=16)
    first_downbeat_index: int | None = Field(default=None, ge=0)
    tempo_bpm: float | None = None
    first_beat_time: float | None = None


def _ok(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse({"success": True, "data": data, "error": None}, status_code=status_code)


def _failure(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"success": False, "data": None, "error": message}, status_code=status_code)


def register_chart_routes(app: FastAPI, jobs: JobService, data_dir: Path) -> None:
    @app.exception_handler(ChartNotReady)
    async def not_ready(_: Request, error: ChartNotReady) -> JSONResponse:
        return _failure(str(error), 409)

    @app.exception_handler(InvalidRequest)
    async def invalid(_: Request, error: InvalidRequest) -> JSONResponse:
        return _failure(str(error), 400)

    @app.get(f"{API_PREFIX}/tracks/{{track_id}}/chords")
    def get_chords(track_id: str) -> JSONResponse:
        return _ok(chord_view(jobs.repository.get(track_id)).model_dump(mode="json"))

    @app.patch(f"{API_PREFIX}/tracks/{{track_id}}/chart")
    def patch_chart(track_id: str, body: ChartPatch) -> JSONResponse:
        job = jobs.repository.get(track_id)
        saved = jobs.repository.save_edits(job.id, validate_edits(job, body.edits))
        return _ok(chord_view(saved).model_dump(mode="json"))

    @app.patch(f"{API_PREFIX}/tracks/{{track_id}}/grid")
    def patch_grid(track_id: str, body: GridPatch) -> JSONResponse:
        job = jobs.repository.get(track_id)
        if job.status in BUSY_STATUSES:
            return _failure("The track is still being analysed; wait for it to finish", 409)
        try:
            GridSettings(**body.model_dump())
        except ValueError as error:
            raise InvalidRequest(str(error)) from error
        requeued = jobs.repository.requeue_with_options(
            job.id, job.options.model_copy(update=body.model_dump())
        )
        return _ok(track_view(requeued, list(stems_of(requeued))).model_dump(), status_code=202)

    @app.get(f"{API_PREFIX}/tracks/{{track_id}}/evidence")
    def get_evidence(track_id: str, source: str = "mix") -> JSONResponse:
        if source not in EVIDENCE_SOURCES:
            raise InvalidRequest(f"source must be one of {', '.join(EVIDENCE_SOURCES)}")
        chosen: EvidenceSource = source  # type: ignore[assignment]
        profiles = evidence(jobs.repository.get(track_id), chosen)
        return _ok({"source": chosen, "profiles": profiles})

    @app.get(f"{API_PREFIX}/tracks/{{track_id}}/export", response_model=None)
    def export(track_id: str, format: str) -> Response:
        if format not in EXPORT_FORMATS:
            raise InvalidRequest(f"format must be one of {', '.join(EXPORT_FORMATS)}")
        job = jobs.repository.get(track_id)
        prefix = Path(job.filename).stem
        if format == "stems":
            archive = export_stems_zip(job, data_dir / EXPORTS_DIR)
            return FileResponse(
                archive, media_type="application/zip", filename=f"{prefix}-stems.zip"
            )
        if format == "json":
            return Response(
                export_json(job),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{prefix}-analysis.json"'},
            )
        return Response(
            export_text(job),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{prefix}-chart.txt"'},
        )
