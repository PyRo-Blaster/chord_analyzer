"""Make a synthetic jazz-trio track with known chords, beats and stems.

The track loops ii-V-I-VI in C (Dm7 G7 Cmaj7 A7), one bar each, in 4/4. Piano plays
rootless voicings, the bass plays root and fifth, the drums play kick, snare and a
swung ride. It is not music to judge by ear: it is a known input for checking that
each model installs, runs, and returns output in the expected format, and for
measuring run time and memory on a track of realistic length.

Usage:
    uv run --with numpy --with soundfile python spikes/synth_track.py <out_dir> [seconds]

Writes <out_dir>/synthetic.wav, the three stems, and truth.json (chords and beats).
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
TEMPO_BPM = 120
BEATS_PER_BAR = 4
DEFAULT_SECONDS = 300
SEED = 7
SWING_RATIO = 2 / 3  # the off-beat eighth falls two thirds through the beat

# (Harte label, bass MIDI root, piano voicing as MIDI notes): rootless A/B voicings.
PROGRESSION = (
    ("D:min7", 38, (53, 57, 60, 64)),  # F A C E
    ("G:7", 43, (53, 57, 59, 64)),  # F A B E (3, 13, 7... a G13 colour on top)
    ("C:maj7", 36, (52, 55, 59, 62)),  # E G B D
    ("A:7", 45, (55, 59, 61, 66)),  # G B C# F#
)
PIANO_GAIN = 0.12
BASS_GAIN = 0.35
KICK_GAIN = 0.5
SNARE_GAIN = 0.15
RIDE_GAIN = 0.05


def midi_to_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12)


def tone(midi: float, seconds: float, harmonics: tuple[float, ...], decay: float) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    frequency = midi_to_hz(midi)
    wave = sum(
        weight * np.sin(2 * np.pi * frequency * (index + 1) * time)
        for index, weight in enumerate(harmonics)
    )
    attack = np.minimum(1.0, time / 0.005)
    return wave * attack * np.exp(-time / decay)


def noise_hit(seconds: float, decay: float, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return rng.uniform(-1.0, 1.0, time.size) * np.exp(-time / decay)


def kick(seconds: float) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    sweep = 50 + 100 * np.exp(-time / 0.03)
    return np.sin(2 * np.pi * np.cumsum(sweep) / SAMPLE_RATE) * np.exp(-time / 0.15)


def place(track: np.ndarray, sound: np.ndarray, at_seconds: float, gain: float) -> np.ndarray:
    start = int(at_seconds * SAMPLE_RATE)
    end = min(track.size, start + sound.size)
    if start >= track.size:
        return track
    result = track.copy()
    result[start:end] += gain * sound[: end - start]
    return result


def render(seconds: float) -> tuple[dict[str, np.ndarray], dict]:
    rng = np.random.default_rng(SEED)
    beat = 60.0 / TEMPO_BPM
    frames = int(seconds * SAMPLE_RATE)
    piano, bass, drums = np.zeros(frames), np.zeros(frames), np.zeros(frames)
    bar_seconds = beat * BEATS_PER_BAR
    bars = int(seconds // bar_seconds)
    chords, beats, downbeats = [], [], []
    for bar in range(bars):
        start = bar * bar_seconds
        label, bass_root, voicing = PROGRESSION[bar % len(PROGRESSION)]
        chords.append({"start": start, "end": start + bar_seconds, "chord": label})
        downbeats.append(start)
        for note in voicing:  # comp on beat 1 and on the "and" of 2
            piano = place(piano, tone(note, 1.2, (1.0, 0.4, 0.2), 0.5), start, PIANO_GAIN)
            comp_at = start + beat + beat * SWING_RATIO
            piano = place(piano, tone(note, 0.8, (1.0, 0.4, 0.2), 0.3), comp_at, PIANO_GAIN)
        for index in range(BEATS_PER_BAR):
            at = start + index * beat
            beats.append(at)
            bass_note = bass_root if index % 2 == 0 else bass_root + 7
            bass = place(bass, tone(bass_note, beat, (1.0, 0.5, 0.2), 0.4), at, BASS_GAIN)
            drums = place(drums, noise_hit(0.4, 0.15, rng), at, RIDE_GAIN)
            drums = place(drums, noise_hit(0.3, 0.1, rng), at + beat * SWING_RATIO, RIDE_GAIN)
            if index in (0, 2):
                drums = place(drums, kick(0.3), at, KICK_GAIN)
            else:
                drums = place(drums, noise_hit(0.2, 0.05, rng), at, SNARE_GAIN)
    stems = {"piano": piano, "bass": bass, "drums": drums}
    truth = {"tempo_bpm": TEMPO_BPM, "chords": chords, "beats": beats, "downbeats": downbeats}
    return stems, truth


def main(out_dir: str, seconds: float) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stems, truth = render(seconds)
    mix = sum(stems.values())
    peak = float(np.max(np.abs(mix))) or 1.0
    scale = 0.9 / peak
    for name, stem in stems.items():
        sf.write(out / f"{name}.wav", np.column_stack([stem, stem]) * scale, SAMPLE_RATE)
    sf.write(out / "synthetic.wav", np.column_stack([mix, mix]) * scale, SAMPLE_RATE)
    (out / "truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"wrote {seconds:.0f} s of audio, {len(truth['chords'])} bars, to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SECONDS))
