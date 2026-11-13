# Jazz Chord Analyzer — Phased Development and Test Roadmap

Nov 13, 2026 · based on `Jazz Chord Analyzer — Technical Design.md`

This is the roadmap, not the task-level plan. Each phase gets its own detailed plan (bite-sized TDD tasks) written just before it starts, because each phase depends on what the previous gate found.

## What was checked today

**This computer**

| Item | Value |
| --- | --- |
| Chip and memory | Apple M1 Pro, 10 cores, 16 GB unified memory |
| GPU | Apple GPU only (PyTorch MPS). No NVIDIA, no CUDA. |
| Free disk | 37 GB (disk is 92% full) |
| Installed | uv (Python 3.8, 3.11, 3.12, 3.14), Node 24, pnpm 11, ffmpeg 7.1, Docker 29, git |
| Not installed | Redis |

**Packages (PyPI and Hugging Face, Nov 13, 2026)**

| Package | Version | Constraint that matters |
| --- | --- | --- |
| lv-chordia | 1.1.0 | Python 3.8+, torch 2.0+, MIT |
| bs-roformer-infer | 0.1.5 | Python 3.10+, torch 2.0+, MIT |
| audio-separator | 0.48.0 | Python 3.10+, numpy 2+ |
| demucs | 4.1.0 | numpy below 2, torch below 2.3 |
| BTC | not on PyPI | Hugging Face repo `puar-playground/btc-chord` has both checkpoints and the model source, MIT |
| madmom | 0.16.1 | Last release 2018. Licence field: "BSD, CC BY-NC-SA". |
| beat-this | 1.1.0 | torch 2+. Not in the design; a third beat-tracker candidate. |
| mir_eval | 0.8.2 | MIT |

Not checked yet: whether each model runs on MPS, QMUL sax weights, Beat-Transformer install, checkpoint licences. Phase 0 does this.

## What this changes in the design

1. **Isolation by virtual environment, not by container, on this Mac.** PyTorch inside a Docker container on macOS cannot use the Apple GPU. Each model gets its own uv project and is called as a subprocess. The same command-line contract can be wrapped in a container later for a CUDA computer.
2. **The isolation rule is confirmed as needed.** demucs needs numpy below 2 and audio-separator needs numpy 2 or above. They cannot share an environment.
3. **The 53-stem model is unlikely to run here.** It wants 16 GB of VRAM and this computer has 16 GB in total, shared with the system. Treat stage 2b as out of version 1 on this computer unless Phase 0 shows otherwise.
4. **Add beat-this to the beat-tracker comparison.** madmom is hard to install on current Python and its model licence is non-commercial.
5. **Disk is a constraint for Phase 2.** A rough estimate is 200 MB of FLAC stems for each track, so 113 JAAH tracks would need more than 20 GB. The evaluation run keeps only the drum-free mix and the bass stem for each track.
6. **No Redis for a one-user app.** A job table in SQLite and one worker process is enough. Celery or RQ is needed only if other people use the app. Decide in the Phase 3 plan.

## Phase order

```
Phase 0  model spikes ─────┐
                           ├─> Phase 1b  workers + CLI ─> Phase 2  evaluation ─> Phase 3d–3h  chord UI
Phase 1a core library ─────┘                                   │
                                                               └ in parallel: Phase 3a–3c  API, upload, mixer
Phase 4  improvement: after Phase 3, planned later
```

Phase 0 and Phase 1a have no dependency on each other. Phase 3a to 3c do not depend on the Phase 2 decisions, so they can be built while the JAAH audio is collected.

## Test layers

| Layer | What it covers | When it runs | Tools |
| --- | --- | --- | --- |
| Unit | All pure logic: label parsing, Jazz5 mapping, agreement, beat grid, decoder, separation plan, residue, cache key, export, metrics | Every commit, seconds | pytest, hypothesis |
| Contract | Each worker's output files against a schema, using recorded real outputs | Every commit | pytest, pydantic |
| Model smoke | Real models on short synthetic clips | On demand: `pytest -m model` | pytest |
| Pipeline integration | Stage order, cache, resume, failure, with fake workers | Every commit | pytest |
| Real-track run | Whole pipeline with real models on one real track | Once at each phase gate, checked by ear | CLI |
| Evaluation | Accuracy on JAAH and the personal set. An experiment, not a test. | Phase 2 | mir_eval |
| API integration | Endpoints, job states, upload validation, with a fake pipeline | Every commit | FastAPI TestClient |
| Front-end unit | Label display, instrument form, chord editor, time-to-pixel maths | Every commit | Vitest, React Testing Library |
| End to end | Upload, progress, lanes, edit, export on a pre-analysed fixture track | Before each Phase 3 slice is closed | Playwright |

**Rules**

- TDD (test first, see it fail, then implement) applies to everything except the Phase 0 spikes, which are throwaway.
- Coverage target of 80% applies to `core/`, `pipeline/`, `eval/`, `api/` and `web/src`. The thin worker shims are excluded and are covered by the model smoke tests.
- Model outputs are never asserted for accuracy in tests. Tests assert shape and sanity only. Accuracy is a Phase 2 measurement.
- Test audio is generated in code: a click track at a known tempo, sine bass notes with known pitch classes, summed sines as chords and as stems. No copyrighted audio goes into the repository. Real tracks stay in a git-ignored `data/` folder.
- Each real model's raw output for one 20 to 30 second excerpt is saved as a fixture, so that the downstream logic is tested on realistic data without running a model.

## Phase 0: model spikes

**Goal:** prove that each model runs on the target computer, and answer the open questions in the design.

**Build:** one uv project for each model under `workers/`, and one throwaway script for each that runs the model on a real track and prints the output, the run time and the peak memory.

- Separation: BS-RoFormer SW through bs-roformer-infer. Fallbacks in order: audio-separator, Demucs 6-source.
- Chords: lv-chordia with the "full" dictionary, BTC with the large vocabulary.
- Beats: beat-this, madmom, Beat-Transformer, each on one swing track and one ballad.
- Horns: check that weights for the QMUL sax model can be downloaded.

**Test:** by ear and by eye. No automated tests.

**Exit gate:** one table with a row for each model: installs, device used (MPS or CPU), time for a 5-minute track, peak memory, output format, checkpoint licence, go or no-go. This table selects the separator and the beat tracker, and says whether the horn stage is in version 1 on this computer.

**Needed from you:** two test recordings in `data/`: one piano trio and one quartet with a horn.

## Phase 1a: core library

**Goal:** all the logic of the design that needs no model, as a tested Python package.

**Build (`core/`, Python 3.12):**

| Module | Responsibility | Source in the design |
| --- | --- | --- |
| `chords/harte.py` | Parse a Harte label into root, class, extensions, bass | Comparison step 1 |
| `chords/jazz5.py` | Map a chord class to maj, min, dom7, hdim7, dim | Comparison step 2 |
| `chords/agreement.py` | Agreement level A to D for two parsed labels | Agreement table |
| `chords/display.py` | Harte to jazz symbol (D:min7 to Dm7) | Data model section |
| `grid/resample.py` | Chord segments to one label for each beat | Comparison step 3 |
| `grid/snap.py` | Half-beat snap rule, removal of segments shorter than one beat | Decoder steps 1 and 2 |
| `bass/root.py` | Strongest bass pitch class for each beat | Bass root check |
| `decoder/draft.py` | Draft label, review marks, confidence | Decoder steps 3 to 5 |
| `separation/plan.py` | Instrument list to separation plan | "How the list is used" table |
| `separation/residue.py` | Mix minus all stems, same sample rate and length | Processing rules |
| `cache/key.py` | Hash of the audio file plus the instrument list | Processing rules |
| `export/` | Text chart with four bars on each line, JSON | Export |
| `schema/` | Typed records: beat, chord segment, chart record, analysis document. Stem and job records come in Phase 1b and Phase 3. | Chart record |

The task-level plan is `2026-11-13-phase-1a-core-library.md`. It adds four small modules to this table: `pitch.py`, `schema/base.py`, `chords/parts.py` and `grid/beats.py`.

**Test:** unit tests, written first. The two tables in the design (agreement levels, instrument list effects) become parametrised test cases row by row. Property tests cover the invariants: every beat gets exactly one label, the stems plus the residue equal the mix, a snapped change never moves more than half a beat.

**Exit gate:** every row of both design tables passes as a test, and coverage is above 80%.

## Phase 1b: workers and command-line pipeline

**Goal:** the Phase 1 deliverable of the design. One command takes a file and an instrument list and writes stems, beats, both chord outputs and the comparison JSON.

**Build:**

- Worker contract: each worker is a command that takes input paths and a parameter file and writes result files plus `result.json` to an output folder.
- One worker for each model chosen in Phase 0, each in its own uv project.
- Orchestrator in `pipeline/`: runs the stages, writes each stage result, uses the cache, restarts at the failed stage.
- A benchmark command that writes run time and peak memory for each stage.

**Test:**

- Contract tests: recorded outputs from Phase 0 validate against the schemas.
- Orchestrator tests with fake workers: stage order, a cache hit calls no worker, a failed stage keeps the earlier results, a changed instrument list restarts at separation.
- Model smoke tests on synthetic clips: stems have the sample rate and length of the source, the beat tracker finds a 120 BPM click track, each chord model reports root C on a synthetic C major chord.
- One real-track run for each of the two test recordings, validated against the schema and checked by ear.

**Exit gate:** the command works on both test recordings, and the time and memory table for this computer is written.

## Phase 2: evaluation

**Goal:** the four decisions of the evaluation plan, made from data.

**Build (`eval/`):** JAAH annotation loader, the six metrics, a batch runner that can resume, and a report generator that writes the tables and one line for each decision rule.

**Test:**

- Each metric is tested first on a toy case computed by hand. Example: reference C:maj7 for 0 to 4 s, estimate C:maj for 0 to 2 s and C:min for 2 to 4 s gives root accuracy 1.0 and Jazz5 accuracy 0.5.
- The loader is tested on a small sample of JAAH annotations.
- A pilot run on 5 tracks comes before the full run.
- Sanity check on the result: Jazz5 accuracy far outside the published 33–40% range in either direction means an alignment or mapping bug until shown otherwise.

**Exit gate:** a results report with the four decisions: primary model, drum-free input or full mix, decoder kept or not, agreement colours kept or not. These set the scope of Phase 3d onward.

**Needed from you (long lead, start now):** the audio for the JAAH tracks, and the 10 to 20 personal tracks with charts checked by ear.

## Phase 3: web app

**Goal:** the user interface of the design, built as slices that can each be shown.

| Slice | Content | Depends on Phase 2 |
| --- | --- | --- |
| 3a | FastAPI endpoints, job table, worker process, with a fake pipeline | No |
| 3b | Upload panel, instrument form with presets, job progress for each stage | No |
| 3c | Stem mixer and transport with one shared cursor | No |
| 3d | Bar ruler, two chord lanes, chart lane (read only) | Yes |
| 3e | Label editor, model suggestions, saving edits with the original outputs | Yes |
| 3f | Evidence lane (pitch-class heat map) with source switch | No |
| 3g | Export: text chart, JSON, ZIP of stems | Yes |
| 3h | Grid correction: move the downbeat, change the time signature, rerun stages 3 to 5 | Yes |

**Spike before 3c:** sample-accurate playback of 6 or more stems with one cursor, and 50–100% speed without a pitch change. This is the main technical risk in the front end.

**Test:** API integration tests for every endpoint with a temporary SQLite file and folder. Front-end unit tests for the display conversion, the form presets, the editor and the time-to-pixel maths. One Playwright test for the critical flow (upload, progress, lanes, edit a label, export) against a pre-analysed fixture track. One manual run with real models at the end of each slice.

**Exit gate:** the Playwright flow passes, and the same flow works by hand on a real track.

## Phase 4: improvement

Harmony priors, fine-tuning, more export formats. Each item gets its own design after Phase 2 results and real user corrections exist. Not planned now.

## Repository layout

```
core/       pure logic, no model dependencies
workers/    one uv project for each model
pipeline/   orchestrator and command line
eval/       Phase 2 harness
api/        FastAPI app (Phase 3)
web/        React app (Phase 3)
data/       real audio, git-ignored
docs/       design and plans
```

## Detailed plans to write

| Plan | Covers | Written when |
| --- | --- | --- |
| A1 | Phase 0 spikes: `2026-11-13-phase-0-model-spikes.md` | Written |
| A2 | Phase 1a core library: `2026-11-13-phase-1a-core-library.md` | Written. Its code was run: 323 tests pass, coverage 100%. |
| B | Phase 1b workers and command line | After the Phase 0 gate |
| C | Phase 2 evaluation harness | After the Phase 1b gate |
| D | Phase 3a to 3c | In parallel with Phase 2 |
| E | Phase 3d to 3h | After the Phase 2 gate |

## Decisions needed

- [x] Is this M1 Pro the computer that runs the app? Yes (Nov 13, 2026). Isolation is by uv environment, and the 53-stem model is out unless Phase 0 shows otherwise.
- [ ] Two test recordings for Phase 0, in `data/source/` as `trio.<ext>` and `quartet.<ext>`.
- [ ] Confirm or change the twelve decisions at the top of the Phase 1a plan.
- [ ] Start collecting the JAAH audio and choosing the personal test set.
