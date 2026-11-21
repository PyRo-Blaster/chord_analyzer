import numpy as np
import pytest

from jca_core.evidence.chroma import CHROMA_BINS, chroma_per_beat, pitch_class_profile
from jca_core.grid.beats import regular_beat_grid

SAMPLE_RATE = 22050
BEAT_SECONDS = 0.5


def chord(midis: tuple[int, ...], seconds: float = BEAT_SECONDS) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return sum(0.2 * np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * time) for m in midis)


def top_classes(profile: tuple[float, ...], count: int) -> set[int]:
    return set(np.argsort(profile)[-count:].tolist())


def test_a_c_major_triad_has_c_e_and_g_on_top():
    profile = pitch_class_profile(chord((60, 64, 67)), SAMPLE_RATE)
    assert len(profile) == CHROMA_BINS
    assert top_classes(profile, 3) == {0, 4, 7}
    assert max(profile) == pytest.approx(1.0)


def test_a_rootless_d_minor_7_voicing_shows_f_a_c_e():
    profile = pitch_class_profile(chord((53, 57, 60, 64)), SAMPLE_RATE)
    assert top_classes(profile, 4) == {5, 9, 0, 4}


def test_silence_is_all_zero():
    assert pitch_class_profile(np.zeros(SAMPLE_RATE), SAMPLE_RATE) == (0.0,) * CHROMA_BINS
    assert pitch_class_profile(np.zeros(0), SAMPLE_RATE) == (0.0,) * CHROMA_BINS


def test_stereo_is_mixed_down():
    mono = chord((62, 66, 69))
    assert top_classes(pitch_class_profile(np.column_stack([mono, mono]), SAMPLE_RATE), 3) == {
        2,
        6,
        9,
    }


def test_one_profile_for_each_beat():
    grid = regular_beat_grid([0.0, 0.5, 1.0], beats_per_bar=4)
    audio = np.concatenate(
        [chord((60, 64, 67)), chord((65, 69, 72)), np.zeros(int(0.5 * SAMPLE_RATE))]
    )
    profiles = chroma_per_beat(audio, SAMPLE_RATE, grid)
    assert len(profiles) == 3
    assert top_classes(profiles[0], 3) == {0, 4, 7}
    assert top_classes(profiles[1], 3) == {5, 9, 0}
    assert profiles[2] == (0.0,) * CHROMA_BINS
