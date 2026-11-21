"""Audio input and output: one internal format, aligned stems, FLAC storage."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

INTERNAL_SAMPLE_RATE = 44100  # the rate the separator works at
INTERNAL_CHANNELS = 2
SUPPORTED_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a"})
FLAC_SUBTYPE = "PCM_24"
WAV_SUBTYPE = "FLOAT"
FFMPEG_TIMEOUT_SECONDS = 600
FFMPEG_ERROR_LINES = 5


class AudioError(ValueError):
    """An audio file cannot be read, decoded or aligned."""


def check_supported(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise AudioError(f"{path.name}: upload an MP3, WAV, FLAC or M4A file")


def decode_to_wav(source: Path, target: Path) -> Path:
    """Decode any supported upload to 44.1 kHz stereo float WAV with ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioError("ffmpeg is not installed; install it with `brew install ffmpeg`")
    if not source.is_file():
        raise AudioError(f"{source} was not found")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-ar", str(INTERNAL_SAMPLE_RATE), "-ac", str(INTERNAL_CHANNELS),
        "-c:a", "pcm_f32le", str(target),
    ]  # fmt: skip
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False
    )
    if completed.returncode != 0:
        detail = "\n".join(completed.stderr.strip().splitlines()[-FFMPEG_ERROR_LINES:])
        raise AudioError(f"ffmpeg could not decode {source.name}: {detail}")
    return target


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Return (frames, channels) float32 samples and the sample rate."""
    try:
        samples, rate = sf.read(path, dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError) as error:
        raise AudioError(f"cannot read {path}: {error}") from error
    return samples, int(rate)


def conform(stem: np.ndarray, stem_rate: int, *, frames: int, sample_rate: int) -> np.ndarray:
    """Return a new array trimmed or padded with silence to the source frame count."""
    if stem_rate != sample_rate:
        raise AudioError(f"a stem is at {stem_rate} Hz, but the source is at {sample_rate} Hz")
    if len(stem) >= frames:
        return stem[:frames].copy()
    padding = np.zeros((frames - len(stem), stem.shape[1]), dtype=stem.dtype)
    return np.concatenate([stem, padding])


def write_flac(path: Path, samples: np.ndarray, sample_rate: int) -> Path:
    """Write 24-bit FLAC. Values outside -1 to 1 are clipped, not wrapped."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(samples, -1.0, 1.0), sample_rate, subtype=FLAC_SUBTYPE)
    return path


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> Path:
    """Write float WAV, for audio that a model reads next."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, samples, sample_rate, subtype=WAV_SUBTYPE)
    return path
