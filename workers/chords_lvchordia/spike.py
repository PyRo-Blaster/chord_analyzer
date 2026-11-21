"""lv-chordia spike: write the chord segments of one audio file as JSON.

Usage:
    uv run --directory workers/chords_lvchordia python spike.py <audio> <dictionary> <out.json>
The dictionary is "submission" (about 170 chords) or "full" (600 or more chords).
"""

import json
import sys
from pathlib import Path

from lv_chordia.chord_recognition import chord_recognition


def main(audio_path: str, dictionary: str, out_path: str) -> int:
    segments = chord_recognition(audio_path=audio_path, chord_dict_name=dictionary)
    Path(out_path).write_text(json.dumps(segments, indent=2), encoding="utf-8")
    print(f"{len(segments)} segments written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
