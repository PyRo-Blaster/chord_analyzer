"""Write a mix minus some stems, for example the mix without drums.

Usage:
    uv run --with numpy --with soundfile python spikes/mix_minus.py <mix.wav> <out.wav> <stem.wav>...
"""

import sys

import soundfile as sf


def main(mix_path: str, out_path: str, stem_paths: list[str]) -> int:
    result, sample_rate = sf.read(mix_path, always_2d=True)
    for path in stem_paths:
        stem, rate = sf.read(path, always_2d=True)
        if rate != sample_rate or stem.shape != result.shape:
            print(f"MISMATCH: {path} has rate {rate} and shape {stem.shape}", file=sys.stderr)
            return 1
        result = result - stem
    sf.write(out_path, result, sample_rate)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
