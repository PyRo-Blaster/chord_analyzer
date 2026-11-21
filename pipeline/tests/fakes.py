"""A fake runner that plays the part of each model worker."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import soundfile as sf

from jca_pipeline.contract import RESULT_FILE, WorkerRequest, WorkerResult
from jca_pipeline.runner import WorkerFailed

from .synth import SAMPLE_RATE, SynthTrack


@dataclass
class FakeRunner:
    track: SynthTrack
    lv_labels: tuple[str, ...] | None = None  # one for each bar; default: the true chords
    btc_labels: tuple[str, ...] | None = None
    fail: frozenset[str] = frozenset()
    calls: list[WorkerRequest] = field(default_factory=list)

    def workers_called(self) -> list[str]:
        return [request.worker for request in self.calls]

    def run(self, request: WorkerRequest) -> WorkerResult:
        self.calls.append(request)
        if request.worker in self.fail:
            raise WorkerFailed(f"{request.worker}: model exploded", "Traceback: boom")
        out = Path(request.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        outputs = getattr(self, f"_{request.worker}")(out)
        result = WorkerResult(
            worker=request.worker,
            status="ok",
            outputs=outputs,
            seconds=1.5,
            peak_memory_bytes=2_000_000,
            device="cpu",
        )
        (out / RESULT_FILE).write_text(result.model_dump_json(), encoding="utf-8")
        return result

    def _separate_bsroformer(self, out: Path) -> dict[str, str]:
        for name, samples in self.track.stems.items():
            sf.write(out / f"take_{name}.wav", samples, SAMPLE_RATE, subtype="FLOAT")
        return {name: f"take_{name}.wav" for name in self.track.stems}

    def _beats_beatthis(self, out: Path) -> dict[str, str]:
        marks = {"beats": list(self.track.beats), "downbeats": list(self.track.downbeats)}
        (out / "beats.json").write_text(json.dumps(marks), encoding="utf-8")
        return {"beats": "beats.json"}

    def _labels(self, labels: tuple[str, ...] | None) -> list[tuple[float, float, str]]:
        chosen = labels or tuple(label for _, _, label in self.track.chords)
        return [
            (start, end, label)
            for (start, end, _), label in zip(self.track.chords, chosen, strict=True)
        ]

    def _chords_lvchordia(self, out: Path) -> dict[str, str]:
        rows = [
            {"start_time": s, "end_time": e, "chord": c} for s, e, c in self._labels(self.lv_labels)
        ]
        (out / "chords.json").write_text(json.dumps(rows), encoding="utf-8")
        return {"chords": "chords.json"}

    def _chords_btc(self, out: Path) -> dict[str, str]:
        rows = [{"start": s, "end": e, "chord": c} for s, e, c in self._labels(self.btc_labels)]
        (out / "chords.json").write_text(json.dumps(rows), encoding="utf-8")
        return {"chords": "chords.json"}
