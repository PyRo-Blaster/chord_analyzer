"""Mix a click on every beat, and a higher click on every downbeat, over a recording.

Listen to the result to judge a beat tracker by ear.

Usage:
    uv run --with numpy --with soundfile python spikes/click_mix.py <audio.wav> <beats.json> <out.wav>
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

CLICK_SECONDS = 0.03
BEAT_HZ = 1000.0
DOWNBEAT_HZ = 2000.0
CLICK_GAIN = 0.5
MUSIC_GAIN = 0.6


def click(frequency: float, sample_rate: int) -> np.ndarray:
    time = np.arange(int(CLICK_SECONDS * sample_rate)) / sample_rate
    return CLICK_GAIN * np.sin(2 * np.pi * frequency * time) * np.hanning(time.size)


def click_track(times: list[float], frequency: float, frames: int, sample_rate: int) -> np.ndarray:
    burst = click(frequency, sample_rate)
    track = np.zeros(frames)
    for time in times:
        start = round(time * sample_rate)
        if 0 <= start < frames:
            end = min(frames, start + burst.size)
            track[start:end] += burst[: end - start]
    return track


def main(audio_path: str, beats_path: str, out_path: str) -> int:
    audio, sample_rate = sf.read(audio_path, always_2d=True)
    marks = json.loads(Path(beats_path).read_text(encoding="utf-8"))
    clicks = click_track(marks["beats"], BEAT_HZ, len(audio), sample_rate) + click_track(
        marks["downbeats"], DOWNBEAT_HZ, len(audio), sample_rate
    )
    mixed = np.clip(MUSIC_GAIN * audio + clicks[:, np.newaxis], -1.0, 1.0)
    sf.write(out_path, mixed, sample_rate)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
