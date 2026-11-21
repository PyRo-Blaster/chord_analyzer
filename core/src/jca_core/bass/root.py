"""Bass root check: the strongest pitch class of the bass stem on each beat."""

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from jca_core.grid.beats import beat_boundaries
from jca_core.pitch import PITCH_CLASS_COUNT
from jca_core.schema.records import Beat

MIN_BASS_HZ = 40.0  # just under E1, the lowest string of a double bass
MAX_BASS_HZ = 400.0
SILENCE_RMS = 1e-4
ZERO_PADDING_FACTOR = 4
A4_HZ = 440.0
A4_MIDI = 69


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Return a new one-dimensional float array from mono or (frames, channels) audio."""
    if samples.ndim == 1:
        return samples.astype(np.float64)
    if samples.ndim == 2:
        return samples.mean(axis=1, dtype=np.float64)
    raise ValueError(f"Audio must have 1 or 2 dimensions, got {samples.ndim}")


def pitch_class_energies(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Return spectral energy in the bass range, summed into 12 pitch classes."""
    mono = to_mono(samples)
    if mono.size == 0:
        return np.zeros(PITCH_CLASS_COUNT)
    fft_size = ZERO_PADDING_FACTOR * int(2 ** np.ceil(np.log2(mono.size)))
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size), n=fft_size)) ** 2
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    in_range = (frequencies >= MIN_BASS_HZ) & (frequencies <= MAX_BASS_HZ)
    midi = A4_MIDI + PITCH_CLASS_COUNT * np.log2(frequencies[in_range] / A4_HZ)
    pitch_classes = np.round(midi).astype(int) % PITCH_CLASS_COUNT
    return np.bincount(pitch_classes, weights=spectrum[in_range], minlength=PITCH_CLASS_COUNT)


def strongest_pitch_class(samples: np.ndarray, sample_rate: int) -> int | None:
    """Return the pitch class with the most bass energy, or None for silence."""
    mono = to_mono(samples)
    if mono.size == 0 or float(np.sqrt(np.mean(mono**2))) < SILENCE_RMS:
        return None
    energies = pitch_class_energies(mono, sample_rate)
    if float(energies.sum()) <= 0.0:
        return None
    return int(np.argmax(energies))


def bass_pitch_class_per_beat(
    samples: np.ndarray, sample_rate: int, beats: Sequence[Beat]
) -> tuple[int | None, ...]:
    """Return the strongest bass pitch class for each beat of the grid."""
    mono = to_mono(samples)
    frame_edges = tuple(round(edge * sample_rate) for edge in beat_boundaries(beats))
    return tuple(
        strongest_pitch_class(mono[start:end], sample_rate) for start, end in pairwise(frame_edges)
    )
