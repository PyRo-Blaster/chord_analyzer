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

- [ ] `pytest` in `pipeline/` passes with coverage above 80%, and `core/` still passes.
- [ ] `pytest -m model` passes on this computer.
- [ ] `jca-analyze` on the synthetic track writes stems, beats, both chord outputs, `analysis.json` and `chart.txt`, and prints the stage table.
- [ ] A second identical run calls no worker.
- [ ] Part 2 of Phase 0 (the real recordings) is still open and does not block this gate.
