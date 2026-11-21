"""Content keys: a stage reruns only when the inputs in its key change.

The separation key is jca_core.cache.key.stem_cache_key; the upload key is the audio hash.
"""

import hashlib
import json
from collections.abc import Mapping

from jca_core.decoder.draft import PrimaryModel


def _key(stage: str, **parts: object) -> str:
    canonical = json.dumps({"stage": stage, **parts}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def tracking_key(
    audio_sha256: str,
    tracker: str,
    beats_per_bar: int | None,
    first_downbeat_index: int | None,
    *,
    tempo_bpm: float | None = None,
    first_beat_time: float | None = None,
) -> str:
    """Beat tracking reads the full mix, so the stems are not part of this key."""
    return _key(
        "tracking",
        audio=audio_sha256,
        tracker=tracker,
        beats_per_bar=beats_per_bar,
        first_downbeat_index=first_downbeat_index,
        tempo_bpm=tempo_bpm,
        first_beat_time=first_beat_time,
    )


def recognition_key(separation_key: str, chord_input: str, models: Mapping[str, str]) -> str:
    return _key("recognising", separation=separation_key, input=chord_input, models=dict(models))


def decoding_key(
    separation_key: str,
    tracking_key_value: str,
    recognition_key_value: str,
    primary: PrimaryModel,
    has_chordal_instrument: bool,
) -> str:
    return _key(
        "decoded",
        separation=separation_key,
        tracking=tracking_key_value,
        recognition=recognition_key_value,
        primary=primary,
        has_chordal_instrument=has_chordal_instrument,
    )
