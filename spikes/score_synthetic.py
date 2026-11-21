"""Score both chord models on the synthetic track, beat by beat, against the known chords.

Runs the jca_core decoder on the two model outputs and the true beat grid, and
reports root and Jazz5 accuracy for each model and for each agreement level.
A sanity check of the pipeline, not an accuracy result: the track is synthetic.

Usage (from the repository root):
    uv run --directory core python ../spikes/score_synthetic.py \
        <truth.json> <lv_chordia.json> <btc.json> [seconds]
"""

import json
import sys
from collections import Counter
from pathlib import Path

from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import classify
from jca_core.decoder.draft import decode
from jca_core.grid.beats import build_beat_grid
from jca_core.grid.resample import labels_per_beat
from jca_core.schema.records import ChordSegment


def load_segments(path: str, start_key: str, end_key: str) -> tuple[ChordSegment, ...]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        ChordSegment(start=row[start_key], end=row[end_key], label=row["chord"]) for row in rows
    )


def detect_keys(path: str) -> tuple[str, str]:
    first = json.loads(Path(path).read_text(encoding="utf-8"))[0]
    return ("start_time", "end_time") if "start_time" in first else ("start", "end")


def score(estimates: tuple[str, ...], truths: tuple[str, ...]) -> tuple[float, float]:
    pairs = [(parse_chord(e), parse_chord(t)) for e, t in zip(estimates, truths, strict=True)]
    root = sum(e.root_pc == t.root_pc for e, t in pairs) / len(pairs)
    jazz5 = sum(
        e.root_pc == t.root_pc and classify(e.intervals) == classify(t.intervals) for e, t in pairs
    ) / len(pairs)
    return root, jazz5


def main(truth_path: str, lv_path: str, btc_path: str, seconds: float) -> int:
    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    beats = [time for time in truth["beats"] if time < seconds]
    downbeats = [time for time in truth["downbeats"] if time < seconds]
    grid = build_beat_grid(beats, downbeats)
    truth_segments = tuple(
        ChordSegment(start=row["start"], end=row["end"], label=row["chord"])
        for row in truth["chords"]
        if row["start"] < seconds
    )
    truth_labels = labels_per_beat(truth_segments, grid)
    lv = load_segments(lv_path, *detect_keys(lv_path))
    btc = load_segments(btc_path, *detect_keys(btc_path))
    chart = decode(grid, lv, btc, (None,) * len(grid))

    for name, labels in (
        ("lv-chordia", tuple(r.lv_chordia for r in chart)),
        ("BTC", tuple(r.btc for r in chart)),
    ):
        root, jazz5 = score(labels, truth_labels)
        print(f"{name:10s} root {root:6.1%}   Jazz5 {jazz5:6.1%}   ({len(grid)} beats)")

    by_level = Counter()
    correct = Counter()
    for record, true_label in zip(chart, truth_labels, strict=True):
        by_level[record.agreement] += 1
        true_chord = parse_chord(true_label)
        draft_ok = record.draft.root is not None and parse_chord(record.lv_chordia).root_pc == (
            true_chord.root_pc
        )
        correct[record.agreement] += draft_ok
    for level in sorted(by_level):
        share = correct[level] / by_level[level]
        print(f"level {level}: {by_level[level]:4d} beats, draft root correct {share:6.1%}")
    return 0


if __name__ == "__main__":
    seconds_arg = float(sys.argv[4]) if len(sys.argv) > 4 else float("inf")
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], seconds_arg))
