"""The file contract between the pipeline and a model worker.

The pipeline writes <output_dir>/request.json and runs `python worker.py <request.json>`
in the worker's own environment. The worker writes its output files into output_dir,
then <output_dir>/result.json, and exits 0 on success or 1 on error.
"""

from pathlib import PurePosixPath
from typing import Literal, Self

from jca_core.schema.base import FrozenModel
from pydantic import Field, field_validator, model_validator

PROTOCOL_VERSION = 1
REQUEST_FILE = "request.json"
RESULT_FILE = "result.json"

ParamValue = str | int | float | bool


class WorkerRequest(FrozenModel):
    protocol: Literal[1] = PROTOCOL_VERSION
    worker: str = Field(min_length=1)
    inputs: dict[str, str]
    params: dict[str, ParamValue] = Field(default_factory=dict)
    output_dir: str


class WorkerResult(FrozenModel):
    protocol: Literal[1] = PROTOCOL_VERSION
    worker: str = Field(min_length=1)
    status: Literal["ok", "error"]
    outputs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    seconds: float = Field(ge=0)
    peak_memory_bytes: int = Field(ge=0)
    device: str
    versions: dict[str, str] = Field(default_factory=dict)

    @field_validator("outputs")
    @classmethod
    def _plain_file_names(cls, outputs: dict[str, str]) -> dict[str, str]:
        for name in outputs.values():
            path = PurePosixPath(name)
            if not name or path.name != name or name in {".", ".."}:
                raise ValueError(f"output must be a plain file name, got {name!r}")
        return outputs

    @model_validator(mode="after")
    def _error_matches_status(self) -> Self:
        if self.status == "ok" and self.error is not None:
            raise ValueError("an ok result must not carry an error")
        if self.status == "error" and not self.error:
            raise ValueError("an error result must carry an error message")
        return self
