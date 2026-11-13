# Phase 0: Model Spikes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that each model in the design runs on this computer (Apple M1 Pro, 16 GB), measure its run time and memory, and choose the separator, the beat tracker and the horn stage for version 1.

**Architecture:** One uv project for each model under `workers/`, so that no two models share dependencies. Small throwaway scripts in `spikes/` run each model on two real recordings and write JSON. Results go into `docs/phase0-results.md`. The uv projects stay for Phase 1b; the scripts do not.

**Tech Stack:** uv, Python 3.12 (3.11 for madmom and Demucs), ffmpeg, bs-roformer-infer, lv-chordia, BTC from Hugging Face, beat-this, madmom.

**Roadmap:** `docs/superpowers/plans/2026-11-13-phased-roadmap.md`. **Design:** `Jazz Chord Analyzer — Technical Design.md`.

---

## How this plan differs from a normal plan

- **No TDD.** These are spikes. The check is by ear, by eye and by the numbers in the results table. Phase 1b writes the real workers with tests.
- **Some steps find things out.** Where a command depends on what the step before it shows (a help text, a download page), the step says what to look for and what to write down.
- **Time box.** Stop work on any one model after 45 minutes of install trouble, write "does not install" with the error in the results table, and move on. A model that does not install is a result.

## Before you start

- [ ] Task 1 of `2026-11-13-phase-1a-core-library.md` is done (the repository exists and `.gitignore` excludes `data/` and `runs/`).
- [ ] The user has put two recordings in `data/source/`: a piano trio named `trio.<ext>` and a quartet with one horn named `quartet.<ext>`. Any of MP3, WAV, FLAC or M4A. If the folder is empty, stop and ask the user.

All commands start from the repository root, `/Users/chenji/Desktop/CodeSpace/chord_analyzer`.

## What is already known (checked on Nov 13, 2026)

| Model | Install | Interface | Notes |
| --- | --- | --- | --- |
| BS-RoFormer SW | `bs-roformer-infer` 0.1.5 on PyPI, Python 3.10+ | `bs-roformer-infer --input_folder <dir> --store_dir <dir>` | Reads WAV files. Checkpoint is 700 MB, downloaded to `~/.cache/bs-roformer-infer/`. Writes vocals, drums, bass, guitar, piano, other and an instrumental file. |
| lv-chordia | `lv-chordia` 1.1.0 on PyPI | `chord_recognition(audio_path=..., chord_dict_name="full")` | Returns a list of `{"start_time", "end_time", "chord"}`. The README says CUDA is used when available and does not mention MPS. |
| BTC | Hugging Face repo `puar-playground/btc-chord` | `AutoModel.from_pretrained(..., trust_remote_code=True)`, then `model.predict(path)` | Returns a list of `{"start", "end", "chord"}`. The model card says CPU is faster than MPS for this model. |
| beat-this | `beat-this` 1.1.0 on PyPI | `File2Beats(checkpoint_path="final0", device=..., dbn=False)` | Returns beats and downbeats. Not in the design; added as a candidate. |
| madmom | Not usable from PyPI on current Python. Install from `git+https://github.com/CPJKU/madmom.git`. | `RNNDownBeatProcessor`, `DBNDownBeatTrackingProcessor` | The PyPI licence field says "BSD, CC BY-NC-SA". |
| Beat-Transformer | GitHub repo `zhaojw1998/Beat-Transformer`, MIT | A Colab notebook only | Trained on spectrograms demixed by Spleeter. No inference script. |
| QMUL sax model | Unknown | Unknown | The paper (arXiv 2405.16687) says it is Demucs version 3 trained on FiloSax, and that checkpoints are available. No link was found on the abstract page. |

## File structure

```
data/source/                 the user's two recordings (git-ignored)
data/wav/trio/trio.wav       44.1 kHz stereo copies (git-ignored)
data/wav/quartet/quartet.wav
data/excerpt/trio_30s.wav    30-second excerpt for fixtures (git-ignored)
runs/phase0/                 all model outputs and measurements (git-ignored)
spikes/
  measure.sh                 wall time and peak memory of one command
  check_stems.py             stem length, sample rate and residue level
  check_labels.py            chord labels that mir_eval cannot parse
  beat_stats.py              tempo and beats in each bar
  click_mix.py               clicks over the recording, for checking beats by ear
  mix_minus.py               a mix minus some stems
workers/
  separate_bsroformer/       pyproject.toml, uv.lock
  chords_lvchordia/          pyproject.toml, uv.lock, spike.py
  chords_btc/                pyproject.toml, uv.lock, spike.py
  beats_beatthis/            pyproject.toml, uv.lock, spike.py
  beats_madmom/              pyproject.toml, uv.lock, spike.py
fixtures/phase0/             raw model outputs for the excerpt, JSON only (committed)
docs/phase0-results.md       the results table and the decisions
```

---

### Task 1: Test audio and measuring tools

**Files:**
- Create: `spikes/measure.sh`, `spikes/check_stems.py`, `spikes/check_labels.py`, `spikes/beat_stats.py`, `spikes/click_mix.py`, `spikes/mix_minus.py`
- Create: `docs/phase0-results.md`

- [ ] **Step 1: Convert the two recordings to WAV**

```bash
mkdir -p data/wav/trio data/wav/quartet data/excerpt runs/phase0
ffmpeg -y -i data/source/trio.* -ar 44100 -ac 2 data/wav/trio/trio.wav
ffmpeg -y -i data/source/quartet.* -ar 44100 -ac 2 data/wav/quartet/quartet.wav
ffmpeg -y -ss 60 -t 30 -i data/wav/trio/trio.wav data/excerpt/trio_30s.wav
ffprobe -v error -show_entries format=duration -of csv=p=0 data/wav/trio/trio.wav
ffprobe -v error -show_entries format=duration -of csv=p=0 data/wav/quartet/quartet.wav
```

Expected: two durations in seconds. Write both down; every run time is compared with them.

- [ ] **Step 2: Write the measuring script**

Create `spikes/measure.sh`:

```bash
#!/bin/bash
# Run one command and report its wall time and peak memory.
# Usage: spikes/measure.sh <name> <command> [arguments...]
# Writes runs/phase0/<name>.log (output of the command) and runs/phase0/<name>.measure.
set -euo pipefail

name="$1"
shift
mkdir -p runs/phase0
log="runs/phase0/${name}.log"
timing="runs/phase0/${name}.time"

if ! /usr/bin/time -l -o "$timing" "$@" > "$log" 2>&1; then
    echo "FAILED: $name. Last lines of $log:" >&2
    tail -20 "$log" >&2
    exit 1
fi

awk '
    / real / { printf "wall_seconds=%s\n", $1 }
    /maximum resident set size/ { printf "peak_memory_gb=%.2f\n", $1 / 1073741824 }
' "$timing" | tee "runs/phase0/${name}.measure"
```

Then make it executable and try it:

```bash
chmod +x spikes/measure.sh
spikes/measure.sh selftest python3 -c "x = bytearray(200_000_000); print('ok')"
```

Expected: two lines, `wall_seconds=` with a small number and `peak_memory_gb=` near `0.2`.

Peak memory here is the resident memory of the process. Memory that PyTorch takes on the Apple GPU is not all in this number. For a run on MPS, also watch the Memory column for the python process in Activity Monitor and write down the highest value.

- [ ] **Step 3: Write the stem checker**

Create `spikes/check_stems.py`:

```python
"""Check that every stem has the sample rate and length of the source, and report the residue.

Usage:
    uv run --with numpy --with soundfile python spikes/check_stems.py <source.wav> <stem.wav>...
"""

import sys

import numpy as np
import soundfile as sf

SILENCE = 1e-12


def level_db(samples: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(samples**2) + SILENCE))


def main(source_path: str, stem_paths: list[str]) -> int:
    source, source_rate = sf.read(source_path, always_2d=True)
    print(f"source  rate={source_rate}  frames={len(source)}  level={level_db(source):6.1f} dB")
    residue = source
    problems = 0
    for path in stem_paths:
        stem, rate = sf.read(path, always_2d=True)
        aligned = rate == source_rate and stem.shape == source.shape
        problems += 0 if aligned else 1
        mark = "ok" if aligned else "MISMATCH"
        level = level_db(stem)
        print(f"{mark:8s} rate={rate}  frames={len(stem)}  level={level:6.1f} dB  {path}")
        if aligned:
            residue = residue - stem
    print(f"residue level={level_db(residue):6.1f} dB (relative to source: "
          f"{level_db(residue) - level_db(source):+.1f} dB)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
```

- [ ] **Step 4: Write the label checker**

Create `spikes/check_labels.py`:

```python
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
```

- [ ] **Step 5: Write the beat statistics script**

Create `spikes/beat_stats.py`:

```python
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
```

- [ ] **Step 6: Write the click mixer**

Create `spikes/click_mix.py`:

```python
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
```

- [ ] **Step 7: Write the mix-minus script**

Create `spikes/mix_minus.py`:

```python
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
```

- [ ] **Step 8: Start the results file**

Create `docs/phase0-results.md`:

```markdown
# Phase 0 Results

Computer: Apple M1 Pro, 16 GB. Date of the runs: (fill in).

Track lengths: trio (fill in) s, quartet (fill in) s.

## Models

Ratio is run time divided by track length. Fill one row for each run.

| Model | Installs | Device | Track | Run time (s) | Ratio | Peak memory (GB) | Checkpoint licence | Go or no-go |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BS-RoFormer SW | | | | | | | | |
| lv-chordia, full dictionary | | | | | | | | |
| BTC, large vocabulary | | | | | | | | |
| beat-this | | | | | | | | |
| madmom | | | | | | | | |
| Beat-Transformer | | | | | | | | |
| QMUL sax model | | | | | | | | |

## Notes by ear

- Separation (piano bleed, bass, where the horn goes):
- lv-chordia against BTC on the head of each track:
- Beat trackers on swing (beats, downbeats, half-time or double-time errors):

## Chord labels

- lv-chordia labels that mir_eval cannot parse:
- BTC labels that mir_eval cannot parse:

## Answers to the open questions of the design

- QMUL sax model weights (URL, size, licence):
- ChordFormer weights (URL, size, licence):
- Better downbeats on swing, and why:

## Decisions for Phase 1b

- Separator:
- Beat tracker:
- Horn stage in version 1 on this computer (yes or no):
- Device for each model:
- Time for the whole pipeline on a 5-minute track:
- Disk used by checkpoints:
```

- [ ] **Step 9: Commit**

```bash
git add spikes docs/phase0-results.md
git commit -m "chore: add phase 0 spike tools and results file"
```

---

### Task 2: BS-RoFormer SW separation

**Files:**
- Create: `workers/separate_bsroformer/pyproject.toml` (written by uv)

- [ ] **Step 1: Create the environment**

```bash
mkdir -p workers/separate_bsroformer
uv init --bare --python 3.12 --directory workers/separate_bsroformer
uv add --directory workers/separate_bsroformer bs-roformer-infer
uv run --directory workers/separate_bsroformer python -c "import torch; print(torch.__version__, 'mps:', torch.backends.mps.is_available())"
```

Expected: a torch version of 2.0 or later and `mps: True`.

- [ ] **Step 2: Download the checkpoint, so that the download is not in the run time**

```bash
uv run --directory workers/separate_bsroformer bs-roformer-download --model roformer-model-bs-roformer-sw-by-jarredou
```

Expected: a 700 MB file at `~/.cache/bs-roformer-infer/roformer-model-bs-roformer-sw-by-jarredou/BS-Rofo-SW-Fixed.ckpt`.

- [ ] **Step 3: Find the device option**

```bash
uv run --directory workers/separate_bsroformer bs-roformer-infer --help
```

Look for an option that selects the device. If it accepts `mps`, add it to the commands in Step 4 and write "MPS" in the results table. If the only choices are CUDA and CPU, run as written and write "CPU".

- [ ] **Step 4: Separate both recordings**

```bash
spikes/measure.sh bsroformer_trio uv run --directory workers/separate_bsroformer bs-roformer-infer --input_folder "$PWD/data/wav/trio" --store_dir "$PWD/runs/phase0/bsroformer_trio"
spikes/measure.sh bsroformer_quartet uv run --directory workers/separate_bsroformer bs-roformer-infer --input_folder "$PWD/data/wav/quartet" --store_dir "$PWD/runs/phase0/bsroformer_quartet"
find runs/phase0/bsroformer_trio runs/phase0/bsroformer_quartet -name '*.wav'
```

Expected: `wall_seconds` and `peak_memory_gb` for each run, and seven WAV files for each recording: vocals, drums, bass, guitar, piano, other and one instrumental file.

- [ ] **Step 5: Check the alignment and the residue**

```bash
uv run --with numpy --with soundfile python spikes/check_stems.py data/wav/trio/trio.wav $(find runs/phase0/bsroformer_trio -name '*.wav' ! -name '*instrumental*')
uv run --with numpy --with soundfile python spikes/check_stems.py data/wav/quartet/quartet.wav $(find runs/phase0/bsroformer_quartet -name '*.wav' ! -name '*instrumental*')
```

Expected: six lines that start with `ok` for each recording, and a residue level far below the source (about -30 dB or lower), because the six stems of this model should add up to the mix. A line that starts with `MISMATCH` means the stems need trimming or resampling in Phase 1b; write that down.

- [ ] **Step 6: Listen**

Open the stems of both recordings. Write in the results file: how much piano is in the bass stem and the reverse, how clean the drums are, and which stem holds the horn of the quartet (the design expects "other").

- [ ] **Step 7: Measure the fallbacks only if needed**

If the ratio of run time to track length is above 3, or the run failed, measure Demucs as the design's fallback:

```bash
mkdir -p workers/separate_demucs
uv init --bare --python 3.11 --directory workers/separate_demucs
uv add --directory workers/separate_demucs demucs
spikes/measure.sh demucs_trio uv run --directory workers/separate_demucs demucs -n htdemucs_6s -d mps -o "$PWD/runs/phase0/demucs_trio" "$PWD/data/wav/trio/trio.wav"
```

If `-d mps` fails, run again with `-d cpu`. Add a "Demucs 6-source" row to the results table. If the ratio for BS-RoFormer is 3 or below, skip this step.

- [ ] **Step 8: Record and commit**

Fill the BS-RoFormer row of `docs/phase0-results.md`. For the checkpoint licence, read the model page at `https://huggingface.co/enerjazzer/BS-ROFO-SW-Fixed` and write what it states, or "not stated".

```bash
git add workers/separate_bsroformer docs/phase0-results.md
git commit -m "chore: measure BS-RoFormer SW separation on this computer"
```

---

### Task 3: lv-chordia

**Files:**
- Create: `workers/chords_lvchordia/pyproject.toml` (written by uv)
- Create: `workers/chords_lvchordia/spike.py`

- [ ] **Step 1: Create the environment**

```bash
mkdir -p workers/chords_lvchordia
uv init --bare --python 3.12 --directory workers/chords_lvchordia
uv add --directory workers/chords_lvchordia lv-chordia
```

- [ ] **Step 2: Write the spike script**

Create `workers/chords_lvchordia/spike.py`:

```python
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
```

- [ ] **Step 3: Run both dictionaries on both recordings**

```bash
for track in trio quartet; do
  for dictionary in full submission; do
    spikes/measure.sh "lv_${track}_${dictionary}" uv run --directory workers/chords_lvchordia python spike.py "$PWD/data/wav/${track}/${track}.wav" "$dictionary" "$PWD/runs/phase0/lv_${track}_${dictionary}.json"
  done
done
```

Expected: four `.measure` files and four JSON files. Each JSON file is a list of objects with `start_time`, `end_time` and `chord`.

- [ ] **Step 4: Check the labels**

```bash
uv run --with mir_eval python spikes/check_labels.py runs/phase0/lv_trio_full.json
uv run --with mir_eval python spikes/check_labels.py runs/phase0/lv_quartet_full.json
```

Expected: a list of labels with counts and a last line such as `212 segments, 37 distinct labels, 0 invalid`. Write every label marked `INVALID` into the results file. Phase 1b needs a rule for each one, because `jca_core.chords.harte.parse_chord` rejects them.

Also write down: whether the full dictionary gives 9th, 11th, 13th or altered chords at all on these recordings, and how many segments are shorter than one second.

- [ ] **Step 5: Record and commit**

Fill the lv-chordia row of `docs/phase0-results.md` with the times for the full dictionary.

```bash
git add workers/chords_lvchordia docs/phase0-results.md
git commit -m "chore: measure lv-chordia on this computer"
```

---

### Task 4: BTC

**Files:**
- Create: `workers/chords_btc/pyproject.toml` (written by uv)
- Create: `workers/chords_btc/spike.py`

BTC loads with `trust_remote_code=True`, which runs Python code from the Hugging Face repository, and the repository loads its checkpoint with `torch.load(weights_only=False)`. Both are pinned to one commit here, and Step 2 reads the code before it runs.

- [ ] **Step 1: Create the environment**

```bash
mkdir -p workers/chords_btc
uv init --bare --python 3.12 --directory workers/chords_btc
uv add --directory workers/chords_btc torch numpy librosa transformers huggingface_hub
```

- [ ] **Step 2: Read the remote code at the pinned commit**

```bash
curl -sL https://huggingface.co/puar-playground/btc-chord/raw/d436f2f664f5107cd987774279b8ce171846e376/modeling_btc.py
```

Read the whole file. Confirm that it only loads the checkpoint, computes features and runs the model: no `subprocess`, no `os.system`, no network call other than the Hugging Face download, no file written outside the cache. If anything else is there, stop and report it to the user.

- [ ] **Step 3: Write the spike script**

Create `workers/chords_btc/spike.py`:

```python
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
```

- [ ] **Step 4: Run on both recordings**

```bash
for track in trio quartet; do
  spikes/measure.sh "btc_${track}" uv run --directory workers/chords_btc python spike.py "$PWD/data/wav/${track}/${track}.wav" "$PWD/runs/phase0/btc_${track}.json"
done
uv run --with mir_eval python spikes/check_labels.py runs/phase0/btc_trio.json
uv run --with mir_eval python spikes/check_labels.py runs/phase0/btc_quartet.json
```

Expected: two JSON files, each a list of objects with `start`, `end` and `chord`, and `0 invalid` from the label check. The first run also downloads the checkpoint, so use the second run for the time.

- [ ] **Step 5: Compare the two models by eye**

Open `runs/phase0/lv_trio_full.json` and `runs/phase0/btc_trio.json` side by side for the head of the tune. Write in the results file: where the roots agree, where they do not, and which model changes chord more often.

- [ ] **Step 6: Record and commit**

Fill the BTC row of `docs/phase0-results.md`.

```bash
git add workers/chords_btc docs/phase0-results.md
git commit -m "chore: measure BTC on this computer"
```

---

### Task 5: Beat trackers

**Files:**
- Create: `workers/beats_beatthis/pyproject.toml` (written by uv), `workers/beats_beatthis/spike.py`
- Create: `workers/beats_madmom/pyproject.toml` (written by uv), `workers/beats_madmom/spike.py`

This task answers the open question of the design: which tracker gives the better downbeats on swing.

- [ ] **Step 1: Create the beat-this environment**

```bash
mkdir -p workers/beats_beatthis
uv init --bare --python 3.12 --directory workers/beats_beatthis
uv add --directory workers/beats_beatthis beat-this
```

- [ ] **Step 2: Write the beat-this spike script**

Create `workers/beats_beatthis/spike.py`:

```python
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
```

- [ ] **Step 3: Run beat-this on CPU and on MPS**

```bash
for track in trio quartet; do
  for device in cpu mps; do
    spikes/measure.sh "beatthis_${track}_${device}" uv run --directory workers/beats_beatthis python spike.py "$PWD/data/wav/${track}/${track}.wav" "$device" "$PWD/runs/phase0/beatthis_${track}_${device}.json"
  done
  python3 spikes/beat_stats.py "runs/phase0/beatthis_${track}_cpu.json"
done
```

Expected: a tempo close to the real tempo of each recording, and most bars with 4 beats for a tune in 4/4. If the MPS run fails, write the error in the results file and keep the CPU result.

- [ ] **Step 4: Create the madmom environment**

```bash
mkdir -p workers/beats_madmom
uv init --bare --python 3.11 --directory workers/beats_madmom
uv add --directory workers/beats_madmom "numpy<2" cython
uv add --directory workers/beats_madmom "madmom @ git+https://github.com/CPJKU/madmom.git"
```

If the build fails, write "does not install" and the last error line in the madmom row, skip Steps 5 and 6 for madmom, and go on.

- [ ] **Step 5: Write the madmom spike script**

Create `workers/beats_madmom/spike.py`:

```python
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
        "downbeats": [
            float(time) for time, position in rows if int(position) == DOWNBEAT_POSITION
        ],
    }
    Path(out_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{len(result['beats'])} beats, {len(result['downbeats'])} downbeats -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
```

- [ ] **Step 6: Run madmom**

```bash
for track in trio quartet; do
  spikes/measure.sh "madmom_${track}" uv run --directory workers/beats_madmom python spike.py "$PWD/data/wav/${track}/${track}.wav" "$PWD/runs/phase0/madmom_${track}.json"
  python3 spikes/beat_stats.py "runs/phase0/madmom_${track}.json"
done
```

- [ ] **Step 7: Check both trackers by ear**

```bash
for track in trio quartet; do
  for tracker in beatthis_${track}_cpu madmom_${track}; do
    uv run --with numpy --with soundfile python spikes/click_mix.py "data/wav/${track}/${track}.wav" "runs/phase0/${tracker}.json" "runs/phase0/${tracker}_clicks.wav"
  done
done
```

Listen to each `_clicks.wav` file at three places: the head, the middle of a solo, and the ending. The high click must fall on beat 1. Write in the results file, for each tracker: beats correct or not, downbeats on beat 1 or shifted (for example on beat 3), and any half-time or double-time section.

- [ ] **Step 8: Decide about Beat-Transformer**

Beat-Transformer needs Spleeter to demix the audio first and has no inference script. Try it only if both beat-this and madmom put the downbeat on the wrong beat for most of a recording. Otherwise write "not tried: needs Spleeter, no inference script" in its row.

- [ ] **Step 9: Record and commit**

Fill the beat-this, madmom and Beat-Transformer rows, and the "Better downbeats on swing" answer.

```bash
git add workers/beats_beatthis workers/beats_madmom docs/phase0-results.md
git commit -m "chore: compare beat trackers on swing recordings"
```

---

### Task 6: Saxophone model and ChordFormer weights

**Files:**
- Modify: `docs/phase0-results.md`

This task answers the open question of the design: are weights available for the QMUL sax model and for ChordFormer.

- [ ] **Step 1: Look for the sax checkpoint**

```bash
curl -sL https://arxiv.org/pdf/2405.16687 | pdftotext - - | grep -n -i -E "http|github|zenodo|huggingface|checkpoint"
```

Follow each link that the paper gives for code, checkpoints or data. Write in the results file: the URL of the checkpoint, its size, its licence and its format. The paper says the model is Demucs version 3 trained on FiloSax.

- [ ] **Step 2: Decide**

- If a checkpoint can be downloaded: create `workers/separate_sax` with `uv init --bare --python 3.11 --directory workers/separate_sax` and `uv add --directory workers/separate_sax demucs`, then follow the README of the checkpoint to separate `data/wav/quartet/quartet.wav`. Measure the run with `spikes/measure.sh sax_quartet <the command from the README>`, listen to the sax stem, and write the exact command in the results file.
- If no checkpoint is found in 30 minutes: write "no public weights found" in the row. The horn stage is then out of version 1 on this computer, because the 53-stem model needs 16 GB of VRAM. Horns stay in the residue stem, which `build_separation_plan` already handles with `Capabilities(sax_model=False, multi_stem=False, text_prompted=False)`.

- [ ] **Step 3: Look for ChordFormer weights**

```bash
curl -sL https://arxiv.org/pdf/2502.11840 | pdftotext - - | grep -n -i -E "http|github|zenodo|huggingface|checkpoint"
```

Write the URL, size and licence in the results file, or "no public weights found". ChordFormer is not in version 1; this is a note for Phase 4.

- [ ] **Step 4: Commit**

```bash
git add docs/phase0-results.md
git commit -m "docs: record sax model and ChordFormer availability"
```

If Step 2 created `workers/separate_sax`, add it to the same commit.

---

### Task 7: Drum-free input and fixtures

**Files:**
- Create: `fixtures/phase0/trio_30s.lv_chordia.json`, `fixtures/phase0/trio_30s.btc.json`, `fixtures/phase0/trio_30s.beats.json`, `fixtures/phase0/versions.txt`

The design feeds both chord models with the mix without drums. This task checks that the flow works and saves real model outputs for the Phase 1b contract tests.

- [ ] **Step 1: Make the drum-free mix**

```bash
uv run --with numpy --with soundfile python spikes/mix_minus.py data/wav/trio/trio.wav runs/phase0/trio_no_drums.wav $(find runs/phase0/bsroformer_trio -name '*drums*.wav')
```

Expected: `wrote runs/phase0/trio_no_drums.wav`. Listen to it: the drums should be gone or far quieter.

- [ ] **Step 2: Run both chord models on the drum-free mix**

```bash
spikes/measure.sh lv_trio_no_drums uv run --directory workers/chords_lvchordia python spike.py "$PWD/runs/phase0/trio_no_drums.wav" full "$PWD/runs/phase0/lv_trio_no_drums.json"
spikes/measure.sh btc_trio_no_drums uv run --directory workers/chords_btc python spike.py "$PWD/runs/phase0/trio_no_drums.wav" "$PWD/runs/phase0/btc_trio_no_drums.json"
```

Open the two outputs next to the full-mix outputs of Tasks 3 and 4. Write in the results file whether the labels change a little or a lot. Phase 2 measures which input is more accurate; this step only shows that the flow works.

- [ ] **Step 3: Save the fixtures from the 30-second excerpt**

```bash
mkdir -p fixtures/phase0
uv run --directory workers/chords_lvchordia python spike.py "$PWD/data/excerpt/trio_30s.wav" full "$PWD/fixtures/phase0/trio_30s.lv_chordia.json"
uv run --directory workers/chords_btc python spike.py "$PWD/data/excerpt/trio_30s.wav" "$PWD/fixtures/phase0/trio_30s.btc.json"
uv run --directory workers/beats_beatthis python spike.py "$PWD/data/excerpt/trio_30s.wav" cpu "$PWD/fixtures/phase0/trio_30s.beats.json"
for worker in separate_bsroformer chords_lvchordia chords_btc beats_beatthis; do
  echo "## $worker"
  uv pip list --directory "workers/$worker" --format freeze
done > fixtures/phase0/versions.txt
```

Expected: three JSON files and a list of package versions for each worker. If Task 5 chose madmom over beat-this, make the beats fixture with the madmom script instead.

- [ ] **Step 4: Commit**

```bash
git add fixtures/phase0 docs/phase0-results.md
git commit -m "test: save raw model outputs as fixtures for phase 1b"
```

---

### Task 8: Results and decisions

**Files:**
- Modify: `docs/phase0-results.md`
- Modify: `docs/superpowers/plans/2026-11-13-phased-roadmap.md` (only if a decision changes the roadmap)

- [ ] **Step 1: Measure the disk used by checkpoints**

```bash
du -sh ~/.cache/bs-roformer-infer ~/.cache/huggingface ~/.cache/torch 2>/dev/null
du -sh workers runs/phase0
df -h . | tail -1
```

Write the totals and the free space in the results file.

- [ ] **Step 2: Fill the decisions**

Complete the "Decisions for Phase 1b" section of `docs/phase0-results.md`:

- **Separator:** BS-RoFormer SW if it runs and its ratio is acceptable to the user; otherwise the fallback that was measured.
- **Beat tracker:** the one with the downbeat on beat 1 for more of both recordings. If they are equal by ear, choose beat-this, because it installs on current Python and its licence is not restricted to non-commercial use.
- **Horn stage:** yes only if Task 6 found and ran a sax checkpoint.
- **Device for each model:** the faster of CPU and MPS from the table.
- **Time for the whole pipeline:** the sum of separation, both chord models and the beat tracker for one recording, scaled to 5 minutes.

- [ ] **Step 3: Check the exit gate**

- [ ] Every model has a filled row, including the ones that failed.
- [ ] Every label marked `INVALID` is listed.
- [ ] The three open questions of the design that belong to this phase are answered: sax weights, ChordFormer weights, beat tracker on swing.
- [ ] The five decisions are written.

- [ ] **Step 4: Update the roadmap if needed**

If the horn stage is out, or the separator is not BS-RoFormer SW, change the matching lines in the "What this changes in the design" section of the roadmap.

- [ ] **Step 5: Commit and report**

```bash
git add docs
git commit -m "docs: record phase 0 results and decisions"
```

Show the user the results table and the five decisions. Phase 1b (workers and command line) is planned from this file.
