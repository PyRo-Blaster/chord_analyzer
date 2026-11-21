# Phase 1b: Workers and Command-Line Pipeline

Nov 21, 2026 · built on `jca_core` (Phase 1a) and the Phase 0 results in `docs/phase0-results.md`.

**Goal:** the Phase 1 deliverable of the design. One command takes an audio file and an instrument list and writes stems, beats, both chord outputs, the comparison JSON and a text chart, with run time and memory for each stage.

**Architecture:** a new uv project `pipeline/` (package `jca_pipeline`) depends on `core/` by path. It runs each model as a separate process in that model's own uv environment under `workers/`, through one small file contract. Everything model-specific that can be tested without a model (raw output parsing, stage logic, caching, restarts) lives in `pipeline/` and runs in CI with fake workers.

**Tech stack:** Python 3.12, uv, numpy, soundfile, pydantic, ffmpeg, pytest.

## Decisions

| # | Topic | Decision |
| --- | --- | --- |
| 1 | Models | From Phase 0: BS-RoFormer SW on MPS, lv-chordia (full dictionary) and BTC (large vocabulary) on CPU, beat-this on CPU. No horn stage: `Capabilities(sax_model=False, multi_stem=False, text_prompted=False)`. |
| 2 | Worker contract | `python worker.py <request.json>`. The request names the inputs, the parameters and an output folder. The worker writes its files there and a `result.json` with status, output file names, seconds, peak memory, device and package versions, and exits 1 on error. |
| 3 | Raw output | Workers write the model's raw output unchanged. Adapters in `pipeline/` parse it, so the parsing is tested in CI against the Phase 0 fixtures. |
| 4 | Unparseable labels | A label that `mir_eval` cannot parse becomes `X` (no chord) with a warning naming the label. The run does not stop. |
| 5 | Restarts | Each stage has a content key built from its inputs. A stage reruns only when its key changes. A changed instrument list reruns separation, recognition and decoding, but not beat tracking, which reads the full mix. A changed time signature reruns tracking and decoding only. This is narrower than the design's "start again at stage 2/3" and gives the same results. |
| 6 | Stem cache | Stems are cached in `<out>/cache/stems/<stem_cache_key>/` and shared between runs. The separator's raw WAV files are deleted after the kept stems are written as 24-bit FLAC. |
| 7 | Residue | The mix minus the kept stems. Separator outputs that are not kept (guitar, vocals, other when not named) therefore stay in the residue, as the design asks. |
| 8 | Chord input | The mix minus the separator's drum output, whether or not drums were named. `--chord-input full-mix` switches to the full mix for the Phase 2 comparison. |
| 9 | Failure | The state file is written after every stage, so a failed stage keeps the earlier results. The error and the last lines of the worker log are recorded in the state file. |
| 10 | Audio format | Every upload is decoded once with ffmpeg to 44.1 kHz stereo WAV, the separator's rate. All stems keep that rate and the exact frame count of the decoded source. |
| 11 | Worker code sharing | Each worker is one self-contained file with a small repeated block for the contract. The environments cannot share a package without coupling their dependencies. |

## Layout

```
pipeline/
  pyproject.toml
  src/jca_pipeline/
    config.py         paths, model choices, capabilities, timeouts
    contract.py       WorkerRequest, WorkerResult
    adapters.py       raw lv-chordia, BTC and beat-tracker output to core types
    runner.py         WorkerRunner protocol, SubprocessRunner
    audio.py          ffmpeg decode, read, conform, write FLAC
    state.py          StageRecord, RunState, load and save
    keys.py           content key for each stage
    stages/ingest.py, separation.py, tracking.py, recognition.py, decoding.py
    orchestrator.py   AnalysisRequest, analyze()
    cli.py            jca-analyze command
  tests/              unit, contract and integration tests with fake workers
  tests/models/       smoke tests on real models, marker "model", not run in CI
workers/<name>/worker.py   one for each model, next to its pyproject.toml
```

Run folder for one track: `<out>/<first 16 hex of the audio hash>/` with `source.wav`, `state.json`, `beats/`, `chords/` and `chart/` (`analysis.json`, `chart.txt`).

## Tasks

Each task is test-first: write the test, see it fail, write the code, see it pass, commit.

1. **Scaffold** `pipeline/` with the path dependency on `core/`, the `model` marker excluded by default, and a coverage gate of 80%.
2. **Contract**: request and result models; round trip; status, outputs and error rules.
3. **Adapters**: lv-chordia rows (`start_time`, `end_time`, `chord`), BTC rows (`start`, `end`, `chord`), tracker output (`beats`, `downbeats`). Tested on the Phase 0 fixtures and on bad input: invalid labels become `X` with a warning, zero-length segments are dropped, beats are sorted and repeats removed, a malformed file raises a clear error.
4. **Runner**: writes `request.json`, runs the command with a timeout, keeps the worker log, validates `result.json`, and raises `WorkerFailed` with the log tail for a non-zero exit, a timeout, a missing result or an error status. Tested with small fake worker scripts run by the current Python.
5. **Audio**: decode with ffmpeg (tests skip if ffmpeg is missing), conform a stem to the source frame count, reject another sample rate, write clipped 24-bit FLAC.
6. **State and keys**: atomic save, load, replace one stage record, record a failure; keys change exactly when their inputs change.
7. **Stages**: ingest (format check, hash, decode); separation (plan, cache hit, kept stems, residue, drum-free mix, raw files removed); tracking (tracker or user time signature); recognition (both models, warnings collected); decoding (bass root from the bass stem, decoder, JSON and text chart).
8. **Orchestrator**: stage order; the second run calls no worker; a failure keeps earlier stages and records the error; a changed instrument list reruns separation, recognition and decoding only; a changed time signature reruns tracking and decoding only.
9. **CLI**: argument parsing and instrument names, a stage table with time and memory, a clear message and exit code 1 on a bad instrument, a missing file or a worker failure.
10. **Workers**: one `worker.py` for each model, following the contract.
11. **Model smoke tests** (`pytest -m model`): stems keep the source rate and length; beat-this finds 120 BPM on a click track; each chord model reports root C on a sustained C major chord.
12. **Real run**: the CLI on the 5-minute synthetic track with the real models, then a second run that must be a full cache hit.
13. **CI**: run the `pipeline/` tests (not the model tests) next to `core/`, with ffmpeg installed.

## Exit gate

- [x] `pytest` in `pipeline/` passes with coverage above 80% (111 tests, 99%), and `core/` still passes (323 tests).
- [x] `pytest -m model` passes on this computer (4 tests, 36 s).
- [x] `jca-analyze` on the synthetic track writes stems, beats, both chord outputs, `analysis.json` and `chart.txt`, and prints the stage table.
- [x] A second identical run calls no worker (1.8 s, every stage cached).
- [ ] Part 2 of Phase 0 (the real recordings) is still open and does not block this gate.

## Results of the real run (Nov 21, 2026)

The 5-minute synthetic trio track, with piano, double bass and drums, on the M1 Pro:

| Stage | Time | Worker | Worker time | Peak memory | Device |
| --- | --- | --- | --- | --- | --- |
| uploaded | 0.4 s | | | | |
| separating | 279.5 s | separate_bsroformer | 276.8 s | 3.0 GB | MPS |
| tracking | 6.4 s | beats_beatthis | 6.0 s | 1.0 GB | CPU |
| recognising | 22.0 s | chords_lvchordia, chords_btc | 14.3 s, 6.6 s | 5.4 GB, 0.7 GB | CPU |
| decoded | 1.1 s | | | | |
| **Total** | **5 min 13 s** | | | | |

- Chart: `Dm7 | G9 | Cmaj7 | A9` on most lines, which matches the voicings (the G and A voicings contain the 9th). A few bars read A7.
- Agreement over 601 beats: A 179, B 255, C 6, D 161; 167 beats marked for review, almost all where BTC reads a rootless voicing as another root.
- The bass check on beat 1 found D, G, C and A, the true roots, in every full bar.
- Disk for one 5-minute track: 101 MB decoded source plus 223 MB of cached stems (the drum-free WAV is half of that).

## Notes for later phases

- beat-this finds no beats in plain sine clicks, so the smoke test uses a short groove instead.
- The worker files are generated from `workers/_template/`; after editing a part, run the build script and `ruff check --fix` (the usage line in `build.py` says how).
