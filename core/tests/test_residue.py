import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from jca_core.separation.residue import compute_residue

FRAMES = 64
CHANNELS = 2


def test_residue_is_the_mix_minus_all_stems():
    mix = np.array([[1.0, 1.0], [0.5, -0.5]])
    piano = np.array([[0.25, 0.5], [0.5, 0.0]])
    bass = np.array([[0.25, 0.25], [0.0, -0.25]])
    expected = np.array([[0.5, 0.25], [0.0, -0.25]])
    np.testing.assert_allclose(compute_residue(mix, [piano, bass]), expected)


def test_with_no_stems_the_residue_is_the_mix():
    mix = np.array([[0.1, -0.2], [0.3, 0.4]])
    np.testing.assert_allclose(compute_residue(mix, []), mix)


def test_residue_keeps_the_shape_of_the_mix():
    mix = np.zeros((FRAMES, CHANNELS))
    assert compute_residue(mix, [np.zeros((FRAMES, CHANNELS))]).shape == (FRAMES, CHANNELS)


def test_a_stem_with_another_length_is_rejected():
    mix = np.zeros((FRAMES, CHANNELS))
    with pytest.raises(ValueError, match="Stem 1 has shape"):
        compute_residue(mix, [np.zeros((FRAMES, CHANNELS)), np.zeros((FRAMES - 1, CHANNELS))])


def test_inputs_are_not_changed():
    mix = np.ones((FRAMES, CHANNELS))
    stem = np.full((FRAMES, CHANNELS), 0.25)
    compute_residue(mix, [stem])
    np.testing.assert_array_equal(mix, np.ones((FRAMES, CHANNELS)))
    np.testing.assert_array_equal(stem, np.full((FRAMES, CHANNELS), 0.25))


@given(st.integers(min_value=0, max_value=2**32 - 1), st.integers(min_value=1, max_value=6))
def test_stems_plus_residue_equal_the_mix(seed, stem_count):
    random = np.random.default_rng(seed)
    mix = random.uniform(-1.0, 1.0, size=(FRAMES, CHANNELS))
    stems = [random.uniform(-1.0, 1.0, size=(FRAMES, CHANNELS)) for _ in range(stem_count)]
    residue = compute_residue(mix, stems)
    np.testing.assert_allclose(residue + sum(stems), mix, atol=1e-12)
