"""beat-this spike: write beats and downbeats of one audio file as JSON.

Usage:
    uv run --directory workers/beats_beatthis python spike.py <audio> <device> <out.json>
The device is "cpu" or "mps".
"""

import json
import sys
from pathlib import Path

from beat_this.inference import File2Beats


def main(audio_path: str, device: str, out_path: str) -> int:
    tracker = File2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = tracker(audio_path)
    result = {
        "beats": [float(time) for time in beats],
        "downbeats": [float(time) for time in downbeats],
    }
    Path(out_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{len(result['beats'])} beats, {len(result['downbeats'])} downbeats -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
