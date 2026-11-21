"""Settings, read from environment variables with safe defaults."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "app"
DEFAULT_MAX_UPLOAD_MB = 500
BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    fake_pipeline: bool = False
    poll_seconds: float = 1.0

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * BYTES_PER_MB

    @classmethod
    def from_env(cls) -> "Settings":
        max_mb = int(os.environ.get("JCA_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB))
        if max_mb < 1:
            raise ValueError("JCA_MAX_UPLOAD_MB must be at least 1")
        return cls(
            data_dir=Path(os.environ.get("JCA_DATA_DIR", DEFAULT_DATA_DIR)),
            max_upload_mb=max_mb,
            fake_pipeline=os.environ.get("JCA_FAKE_PIPELINE", "") == "1",
            poll_seconds=float(os.environ.get("JCA_POLL_SECONDS", "1.0")),
        )
