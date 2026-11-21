"""Stage 5, decoded: bass check, decoder, JSON document and text chart."""

import time
from pathlib import Path

from jca_core.bass.root import bass_pitch_class_per_beat
from jca_core.decoder.draft import PrimaryModel, decode
from jca_core.export.json_export import analysis_to_json
from jca_core.export.text_chart import text_chart
from jca_core.schema.records import AnalysisDocument

from jca_pipeline.audio import read_audio
from jca_pipeline.stages.recognition import load_segments
from jca_pipeline.stages.tracking import load_grid
from jca_pipeline.state import StageRecord

ANALYSIS_FILE = "analysis.json"
CHART_FILE = "chart.txt"


def run_decoding(
    grid_path: Path,
    lv_path: Path,
    btc_path: Path,
    bass_stem: Path | None,
    run_dir: Path,
    key: str,
    primary: PrimaryModel,
    has_chordal_instrument: bool,
) -> StageRecord:
    started = time.monotonic()
    grid = load_grid(grid_path)
    lv = load_segments(lv_path)
    btc = load_segments(btc_path)
    if bass_stem is None:
        bass = (None,) * len(grid)
    else:
        samples, rate = read_audio(bass_stem)
        bass = bass_pitch_class_per_beat(samples, rate, grid)
    chart = decode(
        grid, lv, btc, bass, primary=primary, has_chordal_instrument=has_chordal_instrument
    )
    out = run_dir / "chart"
    out.mkdir(parents=True, exist_ok=True)
    document = AnalysisDocument(beats=grid, lv_chordia=lv, btc=btc, chart=chart)
    analysis = out / ANALYSIS_FILE
    analysis.write_text(analysis_to_json(document), encoding="utf-8")
    chart_path = out / CHART_FILE
    chart_path.write_text(text_chart(chart), encoding="utf-8")
    return StageRecord(
        stage="decoded",
        key=key,
        outputs={"analysis": str(analysis), "chart": str(chart_path)},
        seconds=time.monotonic() - started,
    )
