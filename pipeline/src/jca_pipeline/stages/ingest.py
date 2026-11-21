"""Stage 1, uploaded: decode the upload once to the internal format."""

import time
from pathlib import Path

from jca_pipeline.audio import decode_to_wav
from jca_pipeline.state import StageRecord

SOURCE_FILE = "source.wav"


def run_ingest(audio: Path, run_dir: Path, audio_sha256: str) -> StageRecord:
    started = time.monotonic()
    source = decode_to_wav(audio, run_dir / SOURCE_FILE)
    return StageRecord(
        stage="uploaded",
        key=audio_sha256,
        outputs={"source": str(source)},
        seconds=time.monotonic() - started,
    )
