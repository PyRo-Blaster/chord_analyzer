"""A small synthetic trio track with known stems, chords and beats, for tests."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
BEAT_SECONDS = 0.5  # 120 BPM
BEATS_PER_BAR = 4
# (Harte label, bass MIDI note, piano MIDI notes) for each bar.
BARS = (
    ("D:min7", 38, (53, 57, 60, 65)),
    ("G:7", 43, (53, 59, 62, 65)),
    ("C:maj7", 36, (52, 55, 59, 64)),
    ("C:maj7", 36, (52, 55, 59, 64)),
)


@dataclass(frozen=True)
class SynthTrack:
    mix_path: Path
    stems: dict[str, np.ndarray]  # separator output name -> (frames, 2) float32
    chords: tuple[tuple[float, float, str], ...]
    beats: tuple[float, ...]
    downbeats: tuple[float, ...]

    @property
    def frames(self) -> int:
        return len(self.stems["piano"])


def _tone(midi: int, frames: int) -> np.ndarray:
    time = np.arange(frames) / SAMPLE_RATE
    return np.sin(2 * np.pi * 440.0 * 2.0 ** ((midi - 69) / 12) * time)


def make_track(folder: Path, name: str = "take.wav") -> SynthTrack:
    bar_frames = int(BEAT_SECONDS * BEATS_PER_BAR * SAMPLE_RATE)
    piano = np.concatenate(
        [sum(0.05 * _tone(note, bar_frames) for note in notes) for _, _, notes in BARS]
    )
    bass = np.concatenate([0.3 * _tone(root, bar_frames) for _, root, _ in BARS])
    rng = np.random.default_rng(1)
    drums = 0.02 * rng.uniform(-1.0, 1.0, size=piano.size)
    stereo = {
        name: np.column_stack([signal, signal]).astype(np.float32)
        for name, signal in {"piano": piano, "bass": bass, "drums": drums}.items()
    }
    mix = stereo["piano"] + stereo["bass"] + stereo["drums"]
    folder.mkdir(parents=True, exist_ok=True)
    mix_path = folder / name
    sf.write(mix_path, mix, SAMPLE_RATE, subtype="FLOAT")
    bar_seconds = BEAT_SECONDS * BEATS_PER_BAR
    chords = tuple(
        (index * bar_seconds, (index + 1) * bar_seconds, label)
        for index, (label, _, _) in enumerate(BARS)
    )
    beats = tuple(index * BEAT_SECONDS for index in range(len(BARS) * BEATS_PER_BAR))
    zeros = np.zeros_like(stereo["piano"])
    stems = {**stereo, "vocals": zeros, "guitar": zeros, "other": zeros}
    return SynthTrack(mix_path, stems, chords, beats, beats[::BEATS_PER_BAR])


def make_chord_clip(folder: Path, seconds: float = 8.0) -> Path:
    """A sustained C major chord over a C bass, for the chord model smoke tests."""
    frames = int(seconds * SAMPLE_RATE)
    notes = (36, 48, 52, 55, 60, 64, 67)  # C2 bass, then C3 E3 G3 C4 E4 G4
    signal = sum(0.08 * _tone(note, frames) for note in notes)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "c_major.wav"
    sf.write(path, np.column_stack([signal, signal]).astype(np.float32), SAMPLE_RATE)
    return path


def make_click_track(folder: Path, seconds: float = 12.0) -> Path:
    """A 120 BPM groove (kick, snare, bass note on every beat), for the beat tracker.

    Plain sine clicks are not enough: beat-this is trained on music and finds no beats in them.
    """
    frames = int(seconds * SAMPLE_RATE)
    hit_frames = int(0.25 * SAMPLE_RATE)
    time = np.arange(hit_frames) / SAMPLE_RATE
    rng = np.random.default_rng(3)
    kick = np.sin(2 * np.pi * np.cumsum(50 + 100 * np.exp(-time / 0.03)) / SAMPLE_RATE)
    kick = 0.8 * kick * np.exp(-time / 0.12)
    snare = 0.3 * rng.uniform(-1.0, 1.0, hit_frames) * np.exp(-time / 0.05)
    walking = (36, 40, 43, 45)  # C E G A, one note on each beat
    signal = np.zeros(frames)
    for index in range(int(seconds / BEAT_SECONDS)):
        start = int(index * BEAT_SECONDS * SAMPLE_RATE)
        end = min(frames, start + hit_frames)
        note = 0.3 * _tone(walking[index % BEATS_PER_BAR], hit_frames) * np.exp(-time / 0.2)
        drum = kick if index % 2 == 0 else snare
        signal[start:end] += (drum + note)[: end - start]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "groove.wav"
    sf.write(path, np.column_stack([signal, signal]).astype(np.float32), SAMPLE_RATE)
    return path
