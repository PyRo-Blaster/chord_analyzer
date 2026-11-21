"""madmom spike: write beats and downbeats of one audio file as JSON.

Usage:
    uv run --directory workers/beats_madmom python spike.py <audio> <out.json>
"""

import json
import sys
from pathlib import Path

from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor

FRAMES_PER_SECOND = 100
BEATS_PER_BAR = [3, 4]
DOWNBEAT_POSITION = 1


def main(audio_path: str, out_path: str) -> int:
    activations = RNNDownBeatProcessor()(audio_path)
    tracker = DBNDownBeatTrackingProcessor(beats_per_bar=BEATS_PER_BAR, fps=FRAMES_PER_SECOND)
    rows = tracker(activations)  # each row: time in seconds, position in the bar
    result = {
        "beats": [float(time) for time, _ in rows],
        "downbeats": [float(time) for time, position in rows if int(position) == DOWNBEAT_POSITION],
    }
    Path(out_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{len(result['beats'])} beats, {len(result['downbeats'])} downbeats -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
