# Phase 0 Results

Computer: Apple M1 Pro, 16 GB. Date of the runs: Nov 21, 2026.

**Status: part 1 of 2.** The two real recordings (trio and quartet) are not in `data/source/` yet, so every run below used a synthetic trio track made by `spikes/synth_track.py`: 5 minutes at 120 BPM, a ii-V-I-VI loop in C (Dm7 G7 Cmaj7 A7) with rootless piano voicings, root-and-fifth bass, and kick, snare and swung ride. Its chords, beats and stems are known exactly.

This answers the install, device, time, memory and output-format questions. It does **not** answer the quality questions, which need real jazz: separation bleed, chord accuracy, and beat tracking on swing. Part 2 runs the same commands on the two real recordings and fills in the "Notes by ear" section.

Track length: synthetic, 300 s (and a 60 s excerpt).

## Models

Ratio is run time divided by track length, measured on the 300 s track with one model running at a time. Run time includes loading the model.

| Model | Installs | Device | Run time (s) | Ratio | Peak memory (GB) | Checkpoint licence | Go or no-go |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BS-RoFormer SW | Yes, Python 3.12 | MPS (`--device mps`) | 282 | 0.94 | 2.7 | "unknown" on the Hugging Face card | Go |
| lv-chordia, full dictionary | Yes, Python 3.12 | CPU (default) | 17 | 0.06 | 5.0 | MIT (package) | Go |
| BTC, large vocabulary | Yes, Python 3.12 | CPU (default) | 7 | 0.02 | 0.7 | MIT | Go |
| beat-this (`final0`) | Yes, Python 3.12, after adding `soundfile` | CPU | 6 | 0.02 | 0.9 | Not stated in the package | Go |
| madmom (Git version) | Yes, Python 3.11, numpy below 2 | CPU | 30 | 0.10 | 2.8 | CC BY-NC-SA 4.0 for the model files | Go for personal use only |
| Beat-Transformer | Not tried | | | | | MIT | Not tried: needs Spleeter, no inference script |
| QMUL sax model | No weights found | | | | | | No-go |
| Demucs 6-source | Not tried | | | | | | Not needed: BS-RoFormer ratio is below 3 |

Peak memory is the resident memory of the process. For BS-RoFormer on MPS, part of the model's memory sits on the GPU side and may not all show in this number.

**Install notes**

- beat-this falls back to `soundfile` to read audio, because the installed `torchaudio` (2.11) no longer decodes files on its own, but beat-this does not declare `soundfile` as a dependency. The worker adds it.
- madmom on PyPI (0.16.1, 2018) does not support current Python. The Git version (0.17.dev0) builds on Python 3.11 with `numpy<2` and `cython`.
- beat-this on MPS ran (6.8 s for 60 s) but was slower than CPU (4.4 s), so CPU is the choice.

## Checks on the synthetic track

**Separation (BS-RoFormer SW, 60 s excerpt):** every stem has the sample rate and length of the source. The six stems add up to the mix within -40 dB. Against the true stems, the signal-to-distortion ratio is 21 dB for piano, 16 dB for bass and 11 dB for drums. Guitar, vocals and other come out below -99 dB, as they should for a track without them.

**Chord models, beat by beat against the true chords (600 beats):**

| Input | lv-chordia root | lv-chordia Jazz5 | BTC root | BTC Jazz5 |
| --- | --- | --- | --- | --- |
| Full mix | 100.0% | 100.0% | 56.7% | 55.7% |
| Mix without drums (BS-RoFormer drum stem removed) | 100.0% | 100.0% | 72.8% | 71.8% |

BTC reads the rootless voicings without their bass. For example, on the D minor 7 bars (piano F A C E, bass D) it gives F:maj7. This is the case for the bass root check in the design. Removing the drums helps BTC by 16 points on this track. Phase 2 must test both effects on real jazz.

**Beat trackers (60 s excerpt):** beat-this and madmom both find 120 BPM, put 100% of beats within 70 ms of the true beats, and put 100% of downbeats on beat 1. The synthetic track is too easy to tell them apart; part 2 decides.

**Decoder join:** `jca_core.decoder.decode` runs on both real model outputs without errors.

## Chord labels

- lv-chordia labels that mir_eval cannot parse: none of the 8 distinct labels on the synthetic track (D:min7, G:9, G:7, C:maj7, C:maj9, A:7, A:9, N). The full dictionary has 600 or more labels, so part 2 must check again on real recordings.
- BTC labels that mir_eval cannot parse: none of the 9 distinct labels.
- Output keys differ: lv-chordia gives `start_time`, `end_time`, `chord`; BTC gives `start`, `end`, `chord`. Phase 1b workers convert both to `ChordSegment`.

## Answers to the open questions of the design

- **QMUL sax model weights:** no public weights found. The paper (arXiv 2405.16687) says that all checkpoints are available but links only the lab homepage (aim-qmul.github.io). The first author's GitHub has the FiloSax dataset page and no checkpoint. Searched for 30 minutes.
- **ChordFormer weights:** the repository `mwaseemrandhawa/ChordFormer` includes five fold checkpoints in `cache_data/`. It has no licence file, so it cannot be used outside personal study without asking the author. For Phase 4.
- **Better downbeats on swing:** not answered yet. Both trackers are perfect on the synthetic track. Part 2.

## Disk used

| Item | Size |
| --- | --- |
| BS-RoFormer checkpoint (`~/.cache/bs-roformer-infer`) | 672 MB |
| Other model caches (`~/.cache/torch`, Hugging Face) | about 100 MB |
| Worker environments (`workers/*/.venv`) | 3.4 GB in all, about 1 GB at most each |
| Free disk after Phase 0 | 51 GB |

## Decisions for Phase 1b

- **Separator:** BS-RoFormer SW on MPS. It runs at about real time (0.94), so a 5-minute track takes about 5 minutes.
- **Beat tracker:** beat-this, provisionally. It installs on Python 3.12, it is five times faster than madmom here, and its licence is not restricted to non-commercial use. Part 2 can change this if madmom is clearly better on real swing.
- **Horn stage in version 1 on this computer:** no. No sax weights were found, and the 53-stem model needs 16 GB of VRAM. Horns stay in the residue stem: `Capabilities(sax_model=False, multi_stem=False, text_prompted=False)`.
- **Device for each model:** BS-RoFormer on MPS; lv-chordia, BTC and beat-this on CPU.
- **Time for the whole pipeline on a 5-minute track:** about 5.4 minutes (separation 282 s, lv-chordia 17 s, BTC 7 s, beat-this 6 s), almost all of it separation.

## Notes by ear (part 2, needs the real recordings)

- Separation (piano bleed, bass, where the horn goes):
- lv-chordia against BTC on the head of each track:
- Beat trackers on swing (beats, downbeats, half-time or double-time errors):
