"""The FastAPI app. Every JSON reply is {"success", "data", "error"}."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from jca_pipeline.config import WORKER_TIMEOUT_SECONDS, WORKERS_DIR
from jca_pipeline.runner import SubprocessRunner
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from jca_api.chart_routes import register_chart_routes
from jca_api.config import Settings
from jca_api.fake_runner import FakeModelRunner
from jca_api.jobs import JobNotFound, JobOptions, JobRepository
from jca_api.schemas import catalogue, track_view
from jca_api.service import InvalidUpload, JobService, JobWorker, analyze_with, stems_of

API_PREFIX = "/api"
FLAC_MEDIA_TYPE = "audio/flac"


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse({"success": True, "data": data, "error": None}, status_code=status_code)


def failure(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"success": False, "data": None, "error": message}, status_code=status_code)


def build_service(settings: Settings) -> JobService:
    runner = (
        FakeModelRunner()
        if settings.fake_pipeline
        else SubprocessRunner(WORKERS_DIR, WORKER_TIMEOUT_SECONDS)
    )
    return JobService(
        JobRepository(settings.database_path),
        settings.data_dir,
        analyze_with(runner),
        settings.max_upload_bytes,
    )


def create_app(
    settings: Settings, service: JobService | None = None, start_worker: bool = True
) -> FastAPI:
    jobs = service or build_service(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker = JobWorker(jobs, settings.poll_seconds)
        app.state.worker = worker
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.stop()

    app = FastAPI(title="Jazz Chord Analyzer", lifespan=lifespan)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        return failure(str(error.detail), error.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) or "body" for e in error.errors())
        return failure(f"Missing or invalid field: {fields}", 400)

    @app.exception_handler(JobNotFound)
    async def not_found(_: Request, error: JobNotFound) -> JSONResponse:
        return failure(error.args[0], 404)

    @app.get(f"{API_PREFIX}/instruments")
    def instruments() -> JSONResponse:
        return ok(catalogue().model_dump())

    @app.post(f"{API_PREFIX}/tracks")
    def create_track(
        file: Annotated[UploadFile, File()], options: Annotated[str, Form()]
    ) -> JSONResponse:
        try:
            parsed = JobOptions.model_validate(json.loads(options))
        except (json.JSONDecodeError, ValidationError) as error:
            return failure(f"The options field is not valid: {_short(error)}", 400)
        try:
            job = jobs.submit(file.filename or "", file.file, parsed)
        except InvalidUpload as error:
            return failure(str(error), 400)
        return ok(track_view(job, []).model_dump(), status_code=201)

    @app.get(f"{API_PREFIX}/tracks")
    def list_tracks() -> JSONResponse:
        return ok(
            [track_view(job, list(stems_of(job))).model_dump() for job in jobs.repository.recent()]
        )

    @app.get(f"{API_PREFIX}/tracks/{{track_id}}")
    def get_track(track_id: str) -> JSONResponse:
        job = jobs.repository.get(track_id)
        return ok(track_view(job, list(stems_of(job))).model_dump())

    @app.get(f"{API_PREFIX}/tracks/{{track_id}}/stems/{{name}}", response_model=None)
    def get_stem(track_id: str, name: str, download: bool = False) -> FileResponse | JSONResponse:
        job = jobs.repository.get(track_id)
        path = stems_of(job).get(name)
        if path is None or not path.is_file():
            return failure(f"Track {track_id!r} has no stem named {name!r}", 404)
        filename = f"{Path(job.filename).stem}-{path.name}"
        return FileResponse(
            path,
            media_type=FLAC_MEDIA_TYPE,
            filename=filename,
            content_disposition_type="attachment" if download else "inline",
        )

    register_chart_routes(app, jobs, settings.data_dir)
    return app


def _short(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    return str(error)
