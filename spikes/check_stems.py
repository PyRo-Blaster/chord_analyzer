"""Check that every stem has the sample rate and length of the source, and report the residue.

Usage:
    uv run --with numpy --with soundfile python spikes/check_stems.py <source.wav> <stem.wav>...
"""

import sys

import numpy as np
import soundfile as sf

SILENCE = 1e-12


def level_db(samples: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(samples**2) + SILENCE))


def main(source_path: str, stem_paths: list[str]) -> int:
    source, source_rate = sf.read(source_path, always_2d=True)
    print(f"source  rate={source_rate}  frames={len(source)}  level={level_db(source):6.1f} dB")
    residue = source
    problems = 0
    for path in stem_paths:
        stem, rate = sf.read(path, always_2d=True)
        aligned = rate == source_rate and stem.shape == source.shape
        problems += 0 if aligned else 1
        mark = "ok" if aligned else "MISMATCH"
        level = level_db(stem)
        print(f"{mark:8s} rate={rate}  frames={len(stem)}  level={level:6.1f} dB  {path}")
        if aligned:
            residue = residue - stem
    print(f"residue level={level_db(residue):6.1f} dB (relative to source: "
          f"{level_db(residue) - level_db(source):+.1f} dB)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
