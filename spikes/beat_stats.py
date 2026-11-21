"""Print the tempo and the number of beats in each bar for a beat tracker output.

The input is JSON: {"beats": [seconds, ...], "downbeats": [seconds, ...]}.

Usage:
    python3 spikes/beat_stats.py <beats.json>
"""

import json
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path
from statistics import median


def main(path: str) -> int:
    marks = json.loads(Path(path).read_text(encoding="utf-8"))
    beats, downbeats = marks["beats"], marks["downbeats"]
    if len(beats) < 2:
        print(f"beats={len(beats)}: too few beats to measure a tempo")
        return 1
    tempo = 60.0 / median(later - earlier for earlier, later in pairwise(beats))
    bar_lengths = Counter(
        sum(1 for beat in beats if start <= beat < end) for start, end in pairwise(downbeats)
    )
    print(f"beats={len(beats)}  downbeats={len(downbeats)}  median tempo={tempo:.1f} BPM")
    print(f"first beat={beats[0]:.2f} s  last beat={beats[-1]:.2f} s")
    print("beats in each bar (beats: number of bars):", dict(sorted(bar_lengths.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
