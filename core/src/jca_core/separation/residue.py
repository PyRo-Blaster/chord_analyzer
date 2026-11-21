"""The residue stem: the mix minus every kept stem."""

from collections.abc import Sequence
from functools import reduce

import numpy as np


def compute_residue(mix: np.ndarray, stems: Sequence[np.ndarray]) -> np.ndarray:
    """Return a new array, mix minus all stems. Every stem must have the shape of the mix."""
    for index, stem in enumerate(stems):
        if stem.shape != mix.shape:
            raise ValueError(
                f"Stem {index} has shape {stem.shape}, but the mix has shape {mix.shape}"
            )
    return reduce(np.subtract, stems, mix.astype(np.float64))
