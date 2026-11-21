import numpy as np
import pytest

from jca_core.bass.root import (
    bass_pitch_class_per_beat,
    pitch_class_energies,
    strongest_pitch_class,
)
from jca_core.grid.beats import regular_beat_grid

SAMPLE_RATE = 22050
BEAT_SECONDS = 0.5


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12)


def bass_note(midi: int, seconds: float = BEAT_SECONDS) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    frequency = midi_to_hz(midi)
    return (
        0.5 * np.sin(2 * np.pi * frequency * time)
        + 0.25 * np.sin(2 * np.pi * 2 * frequency * time)
        + 0.1 * np.sin(2 * np.pi * 3 * frequency * time)
    )


@pytest.mark.parametrize("midi", range(28, 52))  # E1, the lowest double bass string, to D#3
def test_strongest_pitch_class_of_a_bass_note(midi):
    assert strongest_pitch_class(bass_note(midi), SAMPLE_RATE) == midi % 12


def test_energies_have_one_value_for_each_pitch_class():
    energies = pitch_class_energies(bass_note(33), SAMPLE_RATE)  # A1
    assert energies.shape == (12,)
    assert int(np.argmax(energies)) == 9


def test_silence_has_no_pitch_class():
    assert strongest_pitch_class(np.zeros(SAMPLE_RATE), SAMPLE_RATE) is None


def test_empty_audio_has_no_pitch_class():
    assert strongest_pitch_class(np.zeros(0), SAMPLE_RATE) is None
    assert pitch_class_energies(np.zeros(0), SAMPLE_RATE).tolist() == [0.0] * 12


def test_audio_too_short_to_hold_a_bass_note_has_no_pitch_class():
    assert strongest_pitch_class(np.ones(4), SAMPLE_RATE) is None


def test_stereo_audio_is_mixed_to_mono():
    note = bass_note(38)  # D2
    stereo = np.column_stack([note, note])
    assert strongest_pitch_class(stereo, SAMPLE_RATE) == 2


def test_audio_with_three_dimensions_is_rejected():
    with pytest.raises(ValueError, match="1 or 2 dimensions"):
        strongest_pitch_class(np.zeros((4, 2, 2)), SAMPLE_RATE)


def test_one_pitch_class_for_each_beat():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
    silence = np.zeros(int(BEAT_SECONDS * SAMPLE_RATE))
    audio = np.concatenate([bass_note(38), bass_note(43), bass_note(36), silence])  # D, G, C
    assert bass_pitch_class_per_beat(audio, SAMPLE_RATE, grid) == (2, 7, 0, None)


def test_beats_after_the_end_of_the_audio_have_no_pitch_class():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
    assert bass_pitch_class_per_beat(bass_note(38), SAMPLE_RATE, grid) == (2, None, None, None)
