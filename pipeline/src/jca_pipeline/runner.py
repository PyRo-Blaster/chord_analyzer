"""Run a model worker in its own environment and read back its result."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from jca_pipeline.contract import REQUEST_FILE, RESULT_FILE, WorkerRequest, WorkerResult

LOG_FILE = "worker.log"
LOG_TAIL_LINES = 20
WORKER_SCRIPT = "worker.py"

CommandFactory = Callable[[Path, Path], list[str]]


class WorkerFailed(RuntimeError):
    """A worker did not produce a valid, successful result."""

    def __init__(self, message: str, log_tail: str = "") -> None:
        super().__init__(message)
        self.log_tail = log_tail


class WorkerRunner(Protocol):
    def run(self, request: WorkerRequest) -> WorkerResult: ...


def uv_command(worker_dir: Path, request_path: Path) -> list[str]:
    """Run the worker with the Python of its own uv project."""
    return ["uv", "run", "--directory", str(worker_dir), "python", WORKER_SCRIPT, str(request_path)]


def python_command(worker_dir: Path, request_path: Path) -> list[str]:
    """Run the worker with the current Python. For tests and for workers without a project."""
    return [sys.executable, str(worker_dir / WORKER_SCRIPT), str(request_path)]


@dataclass(frozen=True)
class SubprocessRunner:
    workers_dir: Path
    timeout_seconds: float
    command: CommandFactory = uv_command

    def run(self, request: WorkerRequest) -> WorkerResult:
        worker_dir = self.workers_dir / request.worker
        if not (worker_dir / WORKER_SCRIPT).is_file():
            raise WorkerFailed(f"There is no worker named {request.worker!r} in {self.workers_dir}")
        out = Path(request.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / RESULT_FILE).unlink(missing_ok=True)
        request_path = out / REQUEST_FILE
        request_path.write_text(request.model_dump_json(indent=2), encoding="utf-8")
        log_path = out / LOG_FILE
        exit_code = self._execute(request.worker, worker_dir, request_path, log_path)
        return _read_result(request.worker, out, exit_code, _tail(log_path))

    def _execute(self, worker: str, worker_dir: Path, request_path: Path, log_path: Path) -> int:
        with log_path.open("w", encoding="utf-8") as log:
            try:
                completed = subprocess.run(
                    self.command(worker_dir, request_path),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise WorkerFailed(
                    f"{worker}: timed out after {self.timeout_seconds:g} s", _tail(log_path)
                ) from error
        return completed.returncode


def _read_result(worker: str, out: Path, exit_code: int, log_tail: str) -> WorkerResult:
    result_path = out / RESULT_FILE
    if not result_path.is_file():
        reason = f"exit code {exit_code}" if exit_code else "exit code 0"
        raise WorkerFailed(f"{worker}: {reason}, and it wrote no {RESULT_FILE}", log_tail)
    try:
        result = WorkerResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise WorkerFailed(f"{worker}: invalid {RESULT_FILE}: {error}", log_tail) from error
    if result.status == "error":
        raise WorkerFailed(f"{worker}: {result.error}", log_tail)
    if exit_code != 0:
        raise WorkerFailed(f"{worker}: exit code {exit_code} with an ok result", log_tail)
    missing = [name for name in result.outputs.values() if not (out / name).is_file()]
    if missing:
        raise WorkerFailed(f"{worker}: output {', '.join(missing)} is missing", log_tail)
    return result


def _tail(log_path: Path) -> str:
    if not log_path.is_file():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-LOG_TAIL_LINES:])
