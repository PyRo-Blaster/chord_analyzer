"""Evidence lane: a 12-row pitch-class profile for each beat."""

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from jca_core.bass.root import SILENCE_RMS, to_mono
from jca_core.grid.beats import beat_boundaries
from jca_core.pitch import PITCH_CLASS_COUNT
from jca_core.schema.records import Beat

CHROMA_BINS = PITCH_CLASS_COUNT
MIN_HZ = 55.0  # A1
MAX_HZ = 4200.0  # about C8: above this, harmonics blur the classes more than they help
A4_HZ = 440.0
A4_MIDI = 69
PROFILE_DECIMALS = 3
_SILENT = (0.0,) * CHROMA_BINS


def pitch_class_profile(samples: np.ndarray, sample_rate: int) -> tuple[float, ...]:
    """Spectral magnitude from 55 Hz to 4.2 kHz summed by pitch class, scaled so the top is 1."""
    mono = to_mono(samples)
    if mono.size == 0 or float(np.sqrt(np.mean(mono**2))) < SILENCE_RMS:
        return _SILENT
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    frequencies = np.fft.rfftfreq(mono.size, d=1.0 / sample_rate)
    in_range = (frequencies >= MIN_HZ) & (frequencies <= MAX_HZ)
    midi = A4_MIDI + CHROMA_BINS * np.log2(frequencies[in_range] / A4_HZ)
    classes = np.round(midi).astype(int) % CHROMA_BINS
    energy = np.bincount(classes, weights=spectrum[in_range], minlength=CHROMA_BINS)
    top = float(energy.max())
    if top <= 0.0:
        return _SILENT
    return tuple(round(float(value) / top, PROFILE_DECIMALS) for value in energy)


def chroma_per_beat(
    samples: np.ndarray, sample_rate: int, beats: Sequence[Beat]
) -> tuple[tuple[float, ...], ...]:
    mono = to_mono(samples)
    edges = tuple(round(edge * sample_rate) for edge in beat_boundaries(beats))
    return tuple(
        pitch_class_profile(mono[start:end], sample_rate) for start, end in pairwise(edges)
    )
