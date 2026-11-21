"""List the chord labels in a model output and flag the ones that mir_eval cannot parse.

Works for lv-chordia and BTC output: a JSON list of segments with a "chord" key.

Usage:
    uv run --with mir_eval python spikes/check_labels.py <chords.json>
"""

import json
import sys
from collections import Counter
from pathlib import Path

import mir_eval.chord


def is_valid(label: str) -> bool:
    try:
        mir_eval.chord.encode(label, reduce_extended_chords=True)
    except mir_eval.chord.InvalidChordException:
        return False
    return True


def main(path: str) -> int:
    segments = json.loads(Path(path).read_text(encoding="utf-8"))
    counts = Counter(segment["chord"] for segment in segments)
    invalid = [label for label in counts if not is_valid(label)]
    for label, count in counts.most_common():
        print(f"{count:5d}  {label:24s} {'INVALID' if label in invalid else 'ok'}")
    print(f"{len(segments)} segments, {len(counts)} distinct labels, {len(invalid)} invalid")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
