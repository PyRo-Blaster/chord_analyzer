# Jazz Chord Analyzer — Technical Design

Nov 13, 2026 · @Ji

## Purpose and scope

Version 1 is a web app that takes an uploaded jazz recording and gives back separated instrument stems and a draft chord chart from two models, shown side by side for the user to correct.

The app is an assistant, not an oracle. Jazz chord recognition is not solved, so the design shows the evidence, shows where the two models disagree, and makes every label editable.

**In scope for version 1**

- Upload of one audio file (MP3, WAV, FLAC, M4A).
- A form where the user names the instruments in the track.
- Stem separation into the named instruments, with a mixer.
- Two chord models on the same audio: lv-chordia and BTC.
- Beat and bar tracking, with chords aligned to the bar grid.
- An editable chord chart, with export.

**Not in scope for version 1**

- Live microphone input.
- Note-level transcription of solos.
- Separation of two similar horns that play at the same time (for example alto and tenor sax).
- Model fine-tuning. This is phase 4.

## Expected accuracy on jazz

Published results put jazz chord accuracy at about half of pop accuracy, so the design assumes that many labels will be wrong.

| Evidence | Result | Source |
| --- | --- | --- |
| Chordino on the JAAH jazz dataset, five-class vocabulary | 32.7% | [JAAH paper](https://ismir2018.ismir.net/doc/pdfs/206_Paper.pdf) |
| CREMA on the same dataset and vocabulary | 40.3% | [JAAH paper](https://ismir2018.ismir.net/doc/pdfs/206_Paper.pdf) |
| Top systems on pop benchmarks, as the JAAH authors state | 70–80% | [JAAH paper](https://ismir2018.ismir.net/doc/pdfs/206_Paper.pdf) |
| Commercial transformer model, maj7 quality, JAAH against RWC-Pop | 0.21 against 0.76 | [SBCM analysis](https://sol.sbc.org.br/index.php/sbcm/article/download/43948/43711/) |
| Same model, min7 quality, JAAH against RWC-Pop | 0.19 against 0.81 | [SBCM analysis](https://sol.sbc.org.br/index.php/sbcm/article/download/43948/43711/) |
| Same model, 7(b9) quality, all datasets | about 0.03 | [SBCM analysis](https://sol.sbc.org.br/index.php/sbcm/article/download/43948/43711/) |

The quality figures in the last three rows count only the frames where the root was correct.

The JAAH authors give three causes: jazz voicings often omit the fifth, a chord symbol is an abstraction that does not require every pitch to sound, and players anticipate or delay the changes. The SBCM authors add that jazz is underrepresented in training data.

**Design consequences**

1. Use two models and show their disagreement. Disagreement marks the bars that need a human ear.
2. Use stems. The bass stem gives root evidence that a rootless piano voicing does not give.
3. Show a core chord class first and the extensions second, each with a confidence value.
4. Make every label editable, and keep the corrections as future training data.

## System architecture

The pipeline has two inputs and six processing stages, and every stage writes a result that the interface can show.

&#91;embedded content: analysis pipeline · 2 inputs, 6 stages\]

The instrument list controls only the separation stage. The four middle stages run in parallel on its output, and the decoder joins them on the bar grid.

| Component | Input | Output |
| --- | --- | --- |
| Stem separation | Audio file, instrument list | One audio stem for each named instrument, plus a residue |
| Bass root check | Bass stem | Strongest bass pitch class for each beat |
| lv-chordia | Mix without drums | Chord labels with root, quality and bass |
| BTC | Mix without drums | Chord labels in Harte notation |
| Beat tracker | Full mix | Beat times and downbeats |
| Jazz decoder | The four results above | One draft chord for each beat, with agreement level and confidence |

## Known-instrument input

The user names the instruments before analysis starts, and this list selects the separation models and the stems to keep.

This replaces automatic instrument detection. It removes one error source, and it stops the separator from producing stems for instruments that are not in the track.

**The form**

- A checklist of common jazz instruments: piano, double bass, electric bass, drums, guitar, vibraphone, alto sax, tenor sax, baritone sax, soprano sax, trumpet, trombone, clarinet, flute, vocals.
- A free-text field for other instruments.
- Presets: piano trio, quartet with one horn, quintet with two horns, big band.
- An optional count for each horn type.

**How the list is used**

| User input | Effect on the pipeline |
| --- | --- |
| Piano, bass, drums only | Run the 6-stem model only. Discard the guitar and vocal outputs. Skip the horn stage. |
| One horn (for example alto sax) | Run the 6-stem model, then run the sax model on the residue. Label the result "alto sax". |
| Two horns from different families (sax and trumpet) | Run the 6-stem model, then take the wind and brass stems from the 53-stem model. |
| Two horns from the same family (alto and tenor sax) | Give one "saxes" stem. Tell the user that the split is not reliable. |
| An instrument with no fixed model (vibraphone) | Offer the text-prompted separator, marked as experimental. |
| No guitar, no vocals | Add the guitar and vocal outputs back to the residue, so that their bleed is not lost. |

The list also helps the chord model. If the track has no piano or guitar, the chord evidence comes from the bass and the horn lines only, and the app shows lower confidence for every chord quality.

## Stem separation

Separation runs as a cascade: the rhythm section comes out first, and the horn models work only on what remains.

| Stage | Model | Output stems | Notes |
| --- | --- | --- | --- |
| 1. Rhythm section | [BS-RoFormer SW](https://github.com/openmirlab/bs-roformer-infer) | Vocals, drums, bass, guitar, piano, other | Listed as the recommended default in its inference toolkit. |
| 2a. One saxophone | [QMUL sax model](https://arxiv.org/pdf/2405.16687) | Sax, other | Trained for a jazz saxophone transcription project. |
| 2b. Mixed horns | [MVSep Mega 53-stem](https://vi-control.net/community/threads/new-open-source-53-stems-audio-splitting-model-available.171774/) | Wind, brass, strings and more | The toolkit notes that upstream recommends at least 16 GB of VRAM. |
| 2c. Other instruments (optional) | [SAM Audio](https://ai.meta.com/samaudio/) | Target and residue, from a text prompt | Generative model with gated checkpoints. Experimental in this design. |

Demucs is not the first choice for stage 1. Its 6-source model is described as experimental by its authors, who report [bleeding and artifacts in the piano stem](https://cdn.jsdelivr.net/gh/facebookresearch/demucs@main/README.md). It stays as a fallback for computers with a small GPU.

**Limits to tell the user**

- Two similar horns that play together cannot be split reliably. Meta states that SAM Audio still has difficulty when it must isolate one instrument from an orchestra.
- Old mono recordings, with all players in one room, give more bleed between stems.
- Public training data is mostly rock and pop. [MoisesDB](https://ismir2023program.ismir.net/static/posters/160.pdf), for example, has jazz only as a small part.

**Processing rules**

- Keep each stem at the sample rate and length of the source file, so that all lanes stay aligned.
- Store stems as FLAC. Cache them by the hash of the audio file plus the instrument list.
- Compute a residue stem (the mix minus all stems) and show it in the mixer. A loud residue shows the user that separation was poor.

## Chord recognition: two models side by side

Version 1 runs lv-chordia and BTC on the same audio and shows both results, because neither model is validated on jazz and their disagreement is useful information.

| Attribute | [lv-chordia](https://github.com/openmirlab/lv-chordia) | [BTC](https://huggingface.co/puar-playground/btc-chord) |
| --- | --- | --- |
| Origin | Large-vocabulary chord transcription by chord structure decomposition, ISMIR 2019 | Bi-directional Transformer for Chord Recognition, ISMIR 2019 |
| Method | Splits the task into sub-tasks, such as root and bass recognition | Self-attention over the full audio sequence, single training phase |
| Decoding | Ensemble of 5 pre-trained networks, then an HMM for smoothing | One network |
| Vocabulary | About 170 chords (default) or 600+ chords ("full" dictionary) | 170 chords (large vocabulary) or 25 chords (major and minor) |
| Jazz chord types | 9th, 11th, 13th and alterations in the "full" dictionary | 6, 7, min7, maj7, sus, dim, aug |
| Output | JSON chord list | List of start, end and chord in Harte notation |
| Stated accuracy | About 80% on pop benchmarks (Billboard, RWC Pop, Beatles) | Root accuracy of about 80–84% on pop test sets |
| Training data | Not stated in the sources checked | Isophonics, Robbie Williams, UsPop2002 (pop and rock) |
| Runtime | Python 3.10+, PyTorch | PyTorch, librosa, transformers |
| Licence | MIT | MIT (original repository) |
| Role in this app | Primary. It has the larger vocabulary and gives the bass note. | Second opinion. It has a different architecture, so its errors are partly independent. |

**Settings for version 1**

- lv-chordia: "full" dictionary.
- BTC: large vocabulary.
- Input to both models: the mix with the drum stem removed. Phase 2 tests this against the full mix, because the models were trained on full mixes.

**How the two outputs are compared**

1. Parse each label into four parts: root, core class, extensions, bass note.
2. Map the core class to five jazz classes: maj, min, dom7, hdim7, dim. This is the Jazz5 vocabulary from the JAAH paper.
3. Resample both outputs to the beat grid, one label for each beat.
4. Give each beat an agreement level:

| Level | Condition | Display |
| --- | --- | --- |
| A | Same root, same class, same extensions | Solid colour |
| B | Same root and class, different extensions | Solid colour, extensions in grey |
| C | Same root, different class | Striped |
| D | Different root | Outlined, marked for review |

The agreement level is not a probability of correctness. Two models with the same pop training can agree and both be wrong. Phase 2 measures how well agreement predicts correctness on the test set.

## Beat grid and jazz decoder

A beat tracker gives the bar grid, and a small decoder turns the two frame-level outputs into one draft chart with a chord for each beat.

**Beat and bar tracking**

- Input: the full mix, plus the drum and bass stems as a second attempt if the first result is unstable.
- Candidates: Beat-Transformer and the madmom downbeat tracker. The open-source [ChordMini](https://github.com/ptnghia-j/ChordMiniApp) app uses both.
- The user can set the time signature, tap the tempo, and move the first downbeat. Swing and rubato sections will need this.

**Decoder steps**

1. Snap each chord change to the nearest beat. Jazz players anticipate or delay changes, so a change within half a beat of a bar line moves to the bar line.
2. Remove segments shorter than one beat.
3. Use the bass stem to check the root. If the strongest bass pitch class on beat 1 differs from both model roots, mark the bar for review.
4. Build the draft label: use lv-chordia where the models agree at level A or B, and mark the bar where they agree only at level C or D.
5. Compute a confidence value from the agreement level and the bass check.

**Two-tier label**

- Tier 1: root and Jazz5 class, for example "C dom7". This tier is shown in large type.
- Tier 2: extensions and bass, for example "b9, bass E". This tier is shown in small type with its own confidence.

**Harmony priors (phase 3)**

A key-aware step can prefer common jazz progressions, for example ii–V–I, when the audio evidence is weak. This step must be optional and visible. A prior makes an unusual reharmonisation less likely to appear, and unusual harmony is often the reason the user studies the track.

## User interface

The main screen is one time-aligned view: stems at the top, chord lanes in the middle, evidence at the bottom, with one playback cursor through all of them.

| Area | Content | User actions |
| --- | --- | --- |
| Upload panel | File drop zone, instrument form, time signature (optional) | Start analysis, see job progress for each stage |
| Stem mixer | One waveform lane for each stem, plus the residue | Solo, mute, volume, download a stem |
| Bar ruler | Bar numbers and beat marks | Move the first downbeat, change the time signature, tap tempo |
| Chord lane 1 | lv-chordia result | Read only |
| Chord lane 2 | BTC result | Read only |
| Chart lane | Draft chart with two-tier labels and agreement colours | Edit a label, split or merge a segment, accept a bar |
| Evidence lane | Pitch-class heat map with 12 rows, from the mix without drums | Switch the source to the piano stem or the bass stem |
| Transport | Play, pause, loop a bar range, speed 50–100% | Loop the bar that is under review |

**Editing**

- A click on a chart label opens a small editor: root, class, extensions, bass.
- The two model suggestions for that bar are one click each.
- Each edit is stored with the original model outputs, so that the corrections can become training data.

**Export**

- Chord chart as text, with four bars on each line.
- JSON with times, beats, both model outputs and the user edits.
- Stems as FLAC or WAV.

MusicXML and iReal Pro export are candidates for a later version.

## Data model and API

Each upload becomes one track with one analysis job, and the job moves through five stages that the interface shows one by one.

**Job stages**

1. `uploaded`: file stored, hash computed.
2. `separating`: stems written.
3. `tracking`: beats and bars written.
4. `recognising`: both chord outputs written.
5. `decoded`: draft chart written. The job is complete.

A failed stage keeps the results of the earlier stages. A new run with a changed instrument list starts again at stage 2. A new run with a changed time signature starts again at stage 3.

**Endpoints**

| Method and path | Purpose |
| --- | --- |
| `POST /tracks` | Upload a file with the instrument list. Returns the track id. |
| `GET /tracks/{id}` | Job stage, progress, and links to results. |
| `GET /tracks/{id}/stems/{name}` | Stream or download one stem. |
| `GET /tracks/{id}/beats` | Beat and downbeat times. |
| `GET /tracks/{id}/chords` | Both model outputs and the draft chart. |
| `PATCH /tracks/{id}/chart` | Save user edits to the chart. |
| `PATCH /tracks/{id}/grid` | Save a corrected downbeat or time signature, then run stages 3 to 5 again. |
| `GET /tracks/{id}/export?format=` | Text chart, JSON, or a ZIP file of stems. |

**Chart record (one for each beat)**

```json
{
  "bar": 9,
  "beat": 1,
  "time": 14.62,
  "lv_chordia": "D:min7",
  "btc": "D:min7",
  "bass_pitch_class": "D",
  "agreement": "A",
  "draft": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
  "confidence": 0.8,
  "user_edit": null
}
```

Chord labels use Harte notation inside the system. The interface converts them to jazz symbols (Dm7, G7b9) for display only.

## Tech stack and hardware

The app is a Python back end with a GPU worker and a React front end, and it can run on one computer.

| Layer | Choice | Reason |
| --- | --- | --- |
| Front end | React, TypeScript, wavesurfer.js, Canvas for the heat map | Waveform lanes and a shared cursor are standard in wavesurfer.js |
| API | FastAPI | Async file upload, typed responses |
| Job queue | Celery or RQ with Redis | Separation takes minutes; the API must not block |
| Audio input and output | ffmpeg, librosa, soundfile | Decode all upload formats to one internal format |
| Separation | bs-roformer-infer or python-audio-separator | Both load BS-RoFormer checkpoints |
| Chord models | lv-chordia, BTC | See the comparison section |
| Chord label tools | mir\_eval | Standard parser and metrics for Harte labels |
| Storage | SQLite for metadata, local disk for audio | Enough for one user; change to Postgres and object storage for more |
| Packaging | Docker Compose with a GPU runtime | Each model pins its own Python dependencies |

**Dependency isolation.** The models need different library versions. Each model runs in its own container or virtual environment and is called as a worker task. This also keeps one broken install from stopping the whole app.

**Hardware**

| Configuration | What runs |
| --- | --- |
| GPU with 16 GB of VRAM or more | All stages, with the 53-stem model |
| GPU with 6–8 GB of VRAM | 6-stem model, sax model, both chord models. No 53-stem model. Measure in phase 1. |
| CPU only | Chord models and beat tracking. Separation is slow; use Demucs as the fallback. Measure in phase 1. |

The 16 GB figure for the 53-stem model comes from its toolkit notes. The other two rows are estimates and are not from a source.

## Evaluation plan

Phase 2 measures both models on jazz with ground truth, so that the choice of primary model rests on data and not on vocabulary size.

**Test sets**

- [JAAH](https://zenodo.org/record/1290737): chord, beat and structure annotations for 113 jazz tracks, made by a jazz musician. The audio is not in the dataset and must be obtained separately.
- A personal set of 10 to 20 tracks that the user knows well, with charts checked by ear. This set shows how the app does on the repertoire that matters.

**Metrics**

| Metric | Question it answers |
| --- | --- |
| Root accuracy | Is the root correct? |
| Jazz5 accuracy | Is the core class correct (maj, min, dom7, hdim7, dim)? |
| Sevenths and tetrads accuracy (mir\_eval) | Are the full four-note chords correct? |
| Accuracy for each chord quality | Which qualities fail (maj7, min7, 7, hdim7, altered dominants)? |
| Accuracy at each agreement level | Does agreement between the models predict correctness? |
| Segmentation score | Are the chord changes at the correct times? |

**Comparisons to run**

1. lv-chordia against BTC, each on the full mix.
2. Full mix against the mix without drums, for each model.
3. Model root against the root from the bass stem.
4. Draft chart from the decoder against each model alone.

**Decision rules**

- The model with the higher Jazz5 accuracy becomes the primary model.
- The drum-free input is kept only if it improves Jazz5 accuracy for the primary model.
- The decoder is kept only if its draft is better than the primary model alone.
- If level A beats are correct much more often than level D beats, the agreement colours stay. If not, they are removed.

No target accuracy is set before phase 2. The published jazz figures of 33–40% on Jazz5 are the baseline to beat.

## Build phases, risks and open questions

The build has four phases, and each phase ends with something that can be used.

1. **Phase 1, pipeline on the command line.** One script takes a file and an instrument list and writes stems, beats, both chord outputs and the comparison JSON. This phase also measures run time and memory on the target hardware.
2. **Phase 2, evaluation.** Run the evaluation plan. Select the primary model, the input type, and decide if the decoder stays.
3. **Phase 3, web app.** Upload, job progress, stem mixer, two chord lanes, chart lane, evidence lane, editing, export.
4. **Phase 4, improvement.** Harmony priors, fine-tuning on JAAH plus the user corrections, more export formats. Live input is a candidate only after this phase.

**Risks**

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Both chord models are trained on pop | Low accuracy on extended and altered chords | Two-tier labels, the evidence lane, editing, fine-tuning in phase 4 |
| The models agree but are wrong | Agreement colours give false confidence | Measure this in phase 2. Remove the colours if agreement does not predict correctness. |
| Beat tracking fails on swing or rubato | The bar grid is wrong, so the chart is wrong | Manual downbeat and tempo controls |
| Separation artifacts change the chord evidence | Wrong roots or qualities from stems | Compare stem input against full-mix input in phase 2 |
| The models need library versions that conflict | Install problems | One container for each model |
| The 53-stem model needs more VRAM than is available | No stage 2b | Use the 6-stem model and the sax model only |
| Model licences differ | Limits on sharing the app | Check each checkpoint licence before any use outside personal use |

**Open questions**

- [ ] Which computer will run the app, and how much VRAM does its GPU have?
- [ ] Is the app for one user on one computer, or will other people use it?
- [ ] Which 10 to 20 tracks go into the personal test set?
- [ ] Is a lead-sheet view (four bars on each line) needed in version 1, or is the timeline view enough?
- [ ] Are weights available for the QMUL sax model and for ChordFormer? Check in phase 1.
- [ ] Which beat tracker gives the better downbeats on swing: Beat-Transformer or madmom? Test in phase 1.

## Sources

- [Audio-aligned jazz harmony dataset (JAAH), ISMIR 2018](https://ismir2018.ismir.net/doc/pdfs/206_Paper.pdf)
- [JAAH dataset on Zenodo](https://zenodo.org/record/1290737)
- [Performance analysis of a convolutional transformer chord model for extended chord qualities, SBCM](https://sol.sbc.org.br/index.php/sbcm/article/download/43948/43711/)
- [lv-chordia repository](https://github.com/openmirlab/lv-chordia)
- [BTC chord model, Hugging Face package](https://huggingface.co/puar-playground/btc-chord)
- [BTC paper, arXiv 1907.02698](https://arxiv.org/pdf/1907.02698)
- [ChordFormer, arXiv 2502.11840](https://arxiv.org/abs/2502.11840)
- [ChordMini app repository](https://github.com/ptnghia-j/ChordMiniApp)
- [bs-roformer-infer repository](https://github.com/openmirlab/bs-roformer-infer)
- [python-audio-separator repository](https://github.com/nomadkaraoke/python-audio-separator)
- [Demucs README](https://cdn.jsdelivr.net/gh/facebookresearch/demucs@main/README.md)
- [MVSep Mega 53-stem model, VI-Control thread](https://vi-control.net/community/threads/new-open-source-53-stems-audio-splitting-model-available.171774/)
- [Saxophone separation and transcription pipeline, arXiv 2405.16687](https://arxiv.org/pdf/2405.16687)
- [SAM Audio, Meta](https://ai.meta.com/samaudio/)
- [SAM Audio limitations, The Decoder](https://the-decoder.com/?p=30413)
- [MoisesDB poster, ISMIR 2023](https://ismir2023program.ismir.net/static/posters/160.pdf)

The JAAH paper, the SBCM paper and the ChordMini repository were read in full. The other entries were read as search extracts, so their details need a check in phase 1.
