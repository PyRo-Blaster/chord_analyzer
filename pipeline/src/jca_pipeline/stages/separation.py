"""Stage 2, separating: run the separator, keep the named stems, write residue and drum-free mix.

Stems are cached by the stem cache key, shared between runs, and stored as FLAC.
"""

import shutil
import time
from pathlib import Path

import numpy as np
from jca_core.separation.plan import SeparationPlan
from jca_core.separation.residue import compute_residue

from jca_pipeline.audio import conform, read_audio, write_flac, write_wav
from jca_pipeline.config import SEPARATOR
from jca_pipeline.contract import WorkerRequest
from jca_pipeline.runner import WorkerRunner
from jca_pipeline.stages.common import StageError, file_slug, metric_of, read_json, write_json
from jca_pipeline.state import StageRecord, WorkerMetric

MANIFEST_FILE = "manifest.json"
RAW_DIR = "raw"
RESIDUE_FILE = "residue.flac"
NO_DRUMS_FILE = "no_drums.wav"  # a WAV, because the chord models read it next
DRUMS_OUTPUT = "drums"
BASS_OUTPUT = "bass"


def run_separation(
    source: Path, plan: SeparationPlan, key: str, cache_dir: Path, runner: WorkerRunner
) -> StageRecord:
    started = time.monotonic()
    stem_dir = cache_dir / "stems" / key
    manifest_path = stem_dir / MANIFEST_FILE
    cached = manifest_path.is_file()
    if not cached:
        _separate(source, plan, stem_dir, runner)
    manifest = read_json(manifest_path)
    return StageRecord(
        stage="separating",
        key=key,
        outputs=_outputs(stem_dir, manifest),
        seconds=time.monotonic() - started,
        workers=tuple(WorkerMetric.model_validate(metric) for metric in manifest["workers"]),
        warnings=plan.warnings,
        cached=cached,
    )


def _separate(source: Path, plan: SeparationPlan, stem_dir: Path, runner: WorkerRunner) -> None:
    raw_dir = stem_dir / RAW_DIR
    result = runner.run(
        WorkerRequest(
            worker=SEPARATOR.worker,
            inputs={"mix": str(source)},
            params=SEPARATOR.params,
            output_dir=str(raw_dir),
        )
    )
    mix, rate = read_audio(source)

    def load(output: str) -> np.ndarray:
        if output not in result.outputs:
            raise StageError(f"The separator wrote no '{output}' stem")
        samples, stem_rate = read_audio(raw_dir / result.outputs[output])
        return conform(samples, stem_rate, frames=len(mix), sample_rate=rate)

    kept = {request.name: load(request.source) for request in plan.rhythm_stems}
    stem_files = {name: f"{file_slug(name)}.flac" for name in kept}
    for name, samples in kept.items():
        write_flac(stem_dir / stem_files[name], samples, rate)
    write_flac(stem_dir / RESIDUE_FILE, compute_residue(mix, list(kept.values())), rate)
    drums = [load(DRUMS_OUTPUT)] if DRUMS_OUTPUT in result.outputs else []
    write_wav(stem_dir / NO_DRUMS_FILE, compute_residue(mix, drums), rate)
    bass = next((r.name for r in plan.rhythm_stems if r.source == BASS_OUTPUT), None)
    write_json(
        stem_dir / MANIFEST_FILE,
        {
            "stems": stem_files,
            "bass": bass,
            "residue": RESIDUE_FILE,
            "no_drums": NO_DRUMS_FILE,
            "workers": [metric_of(result).model_dump()],
        },
    )
    shutil.rmtree(raw_dir)


def _outputs(stem_dir: Path, manifest: dict) -> dict[str, str]:
    stems = {f"stem:{name}": str(stem_dir / file) for name, file in manifest["stems"].items()}
    bass = {"bass": str(stem_dir / manifest["stems"][manifest["bass"]])} if manifest["bass"] else {}
    return {
        **stems,
        **bass,
        "residue": str(stem_dir / manifest["residue"]),
        "no_drums": str(stem_dir / manifest["no_drums"]),
    }
