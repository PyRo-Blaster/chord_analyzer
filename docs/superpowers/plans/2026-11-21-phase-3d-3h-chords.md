# Phase 3d–3h: Chord Chart, Editing, Evidence, Export and Grid

Nov 21, 2026 · built on Phase 3a–3c (`api/`, `web/`).

**Goal:** the rest of the user interface in the design. The user reads both model outputs and the draft chart on the bar grid, sees where the models disagree, checks the pitch evidence, corrects labels (with the model suggestions one click away), fixes the bar grid, and exports the chart, the JSON and the stems.

**Architecture:** the API serves the decoded chart with the user's edits applied, stores edits per job in the job table, recomputes nothing on an edit, and requeues the job for a grid change; the pipeline's content keys then rerun only tracking and decoding. The web app shows a bar-grid chart view under the mixer and shares the mixer's playback engine.

## Decisions

| # | Topic | Decision |
| --- | --- | --- |
| 1 | Layout | Chords are shown as a bar grid, four bars on each line (the lead-sheet view from the design's open questions), under the stem mixer. Each bar holds the chart lane, the two model lanes, the bass note and a strip of the evidence lane. Continuous chord lanes under the waveforms would need zoom and scroll to be readable on a 5-minute track (about 150 bars). The bar grid shares the mixer's cursor: the playing beat is highlighted, and clicking a bar number seeks there. |
| 2 | Symbols | The API adds jazz symbols (Dm7, G7b9) to every label it sends, using `jca_core.chords.display`. The web app does not repeat that logic. |
| 3 | Two-tier label | Tier 1 is the root and the Jazz5 class in large type ("D min"); tier 2 is the extensions and a bass that differs from the root, in small type ("b7, bass C"), with its own confidence. |
| 4 | Agreement display | A: solid; B: solid with the extensions in grey; C: striped; D: outlined and marked for review. A bar that failed the bass check also gets the review mark. |
| 5 | Edits | An edit sets `user_edit` on one or more beats. A segment is a run of beats with the same label, so a split is an edit of part of a segment and a merge is an edit across segments. "Accept" copies the draft into `user_edit`. Edits are stored in the job row with the beat time, so the original model outputs and the draft stay unchanged next to each edit (training data for phase 4). |
| 6 | Edits after a grid change | Edits are matched to beats by time, within 60 ms. Edits that no longer match a beat are kept and counted as unplaced, never deleted. |
| 7 | Grid change | `PATCH /grid` saves the time signature, the first downbeat and an optional tapped tempo, and puts the job back in the queue. Separation and recognition are reused through their keys; tracking and decoding rerun. |
| 8 | Tap tempo | Tapping gives a tempo and the time of the first tap. The tracking stage then builds a constant-tempo grid from that time to the end of the track instead of running the tracker. This is for tracks where the tracker fails; rubato still needs the tracker. |
| 9 | Evidence | A 12-row pitch-class profile for each beat (FFT energy from 55 Hz to 4.2 kHz, summed by pitch class, scaled to its loudest class), computed on request from the drum-free mix, the piano stem or the bass stem, and cached for each source and grid. |
| 10 | Export | `?format=text` (the text chart with edits), `?format=json` (the analysis document with edits), `?format=stems` (a ZIP of the FLAC stems and the residue). WAV stems are left for later; FLAC opens in every audio editor checked. |

## Tasks

1. **Pipeline:** a tempo override (`tempo_bpm`, `first_beat_time`) in `AnalysisRequest`, the tracking key and the tracking stage.
2. **Core:** `jca_core.evidence.chroma.chroma_per_beat`.
3. **API data:** edits and the new grid fields in the job table (with a migration for existing tables); requeue for a grid change.
4. **API views:** the chord view (records, symbols, two tiers, edits applied, unplaced count), edit validation, evidence, exports.
5. **API routes:** `GET /chords`, `PATCH /chart`, `PATCH /grid`, `GET /evidence?source=`, `GET /export?format=`.
6. **Web model:** bars from records, segments in a bar, selection across beats, optimistic edits.
7. **Web views:** chart view with bar cells, label editor with model suggestions, evidence strips with a source switch, grid controls with tap tempo, export links, loop a bar.
8. **End to end:** edit a bar, export the text chart, change the time signature and see the job rerun.

## Exit gate

- [ ] Unit tests pass with coverage above 80% in every package.
- [ ] The Playwright flow covers editing, export and a grid change.
- [ ] By hand with the real models: the synthetic track shows Dm7 | G9 | Cmaj7 | A9, an edit survives a reload, and a change to 3/4 reruns only tracking and decoding.
