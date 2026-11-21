"""BTC spike: write the chord segments of one audio file as JSON.

Usage:
    uv run --directory workers/chords_btc python spike.py <audio> <out.json>
"""

import json
import sys
from pathlib import Path

from transformers import AutoModel

REPOSITORY = "puar-playground/btc-chord"
# trust_remote_code runs code from the repository, so the commit is pinned.
REVISION = "d436f2f664f5107cd987774279b8ce171846e376"


def main(audio_path: str, out_path: str) -> int:
    model = AutoModel.from_pretrained(REPOSITORY, revision=REVISION, trust_remote_code=True)
    segments = model.predict(audio_path)
    Path(out_path).write_text(json.dumps(segments, indent=2), encoding="utf-8")
    print(f"{len(segments)} segments written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
