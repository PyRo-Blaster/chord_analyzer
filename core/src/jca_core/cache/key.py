"""Cache keys: stems are cached by the audio hash plus the instrument list."""

import hashlib
import json
import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from jca_core.separation.plan import Instrument, normalise_other

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def file_sha256(path: Path) -> str:
    """Return the SHA-256 of a file, read in chunks."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def stem_cache_key(
    audio_sha256: str,
    separator: str,
    instruments: Collection[Instrument],
    *,
    horn_counts: Mapping[Instrument, int] | None = None,
    other: Sequence[str] = (),
) -> str:
    """Return one key for the audio, the separator and the instrument list, in any order."""
    if not _SHA256_PATTERN.fullmatch(audio_sha256):
        raise ValueError("audio_sha256 must be 64 lowercase hex characters")
    if not separator:
        raise ValueError("separator must not be empty")
    payload = {
        "audio": audio_sha256,
        "separator": separator,
        "instruments": sorted({instrument.value for instrument in instruments}),
        "horn_counts": sorted(
            [instrument.value, count]
            for instrument, count in (horn_counts or {}).items()
            if count != 1
        ),
        "other": sorted(normalise_other(other)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
