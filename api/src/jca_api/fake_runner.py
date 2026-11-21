"""Stand-in models for development and end-to-end tests (JCA_FAKE_PIPELINE=1).

It answers the worker contract like the real models do, but in a second: the separator
splits the mix by fixed shares, the tracker returns a 120 BPM grid, and both chord models
return C major. The real orchestrator, stages, cache and state file all still run.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf
from jca_pipeline.contract import RESULT_FILE, WorkerRequest, WorkerResult

STEM_SHARES = {"piano": 0.5, "bass": 0.3, "drums": 0.2, "vocals": 0.0, "guitar": 0.0, "other": 0.0}
BEAT_SECONDS = 0.5
BEATS_PER_BAR = 4
FAKE_LABEL = "C:maj"


@dataclass(frozen=True)
class FakeModelRunner:
    delay_seconds: float = 0.5  # so that the progress display has something to show

    def run(self, request: WorkerRequest) -> WorkerResult:
        time.sleep(self.delay_seconds)
        out = Path(request.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        audio = Path(next(iter(request.inputs.values())))
        outputs = _WRITERS[request.worker](audio, out)
        result = WorkerResult(
            worker=request.worker,
            status="ok",
            outputs=outputs,
            seconds=self.delay_seconds,
            peak_memory_bytes=0,
            device="fake",
        )
        (out / RESULT_FILE).write_text(result.model_dump_json(), encoding="utf-8")
        return result


def _separate(audio: Path, out: Path) -> dict[str, str]:
    mix, rate = sf.read(audio, dtype="float32", always_2d=True)
    for name, share in STEM_SHARES.items():
        sf.write(out / f"mix_{name}.wav", mix * share, rate, subtype="FLOAT")
    return {name: f"mix_{name}.wav" for name in STEM_SHARES}


def _beats(audio: Path, out: Path) -> dict[str, str]:
    duration = sf.info(audio).duration
    beats = [index * BEAT_SECONDS for index in range(int(duration / BEAT_SECONDS))]
    marks = {"beats": beats, "downbeats": beats[::BEATS_PER_BAR]}
    (out / "beats.json").write_text(json.dumps(marks), encoding="utf-8")
    return {"beats": "beats.json"}


def _chords(start_key: str, end_key: str):
    def write(audio: Path, out: Path) -> dict[str, str]:
        rows = [{start_key: 0.0, end_key: sf.info(audio).duration, "chord": FAKE_LABEL}]
        (out / "chords.json").write_text(json.dumps(rows), encoding="utf-8")
        return {"chords": "chords.json"}

    return write


_WRITERS = {
    "separate_bsroformer": _separate,
    "beats_beatthis": _beats,
    "chords_lvchordia": _chords("start_time", "end_time"),
    "chords_btc": _chords("start", "end"),
}
