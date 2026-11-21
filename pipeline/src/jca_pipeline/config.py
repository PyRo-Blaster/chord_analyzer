"""Model choices for version 1 on the target computer (see docs/phase0-results.md)."""

from dataclasses import dataclass, field
from pathlib import Path

from jca_core.separation.plan import Capabilities

from jca_pipeline.contract import ParamValue

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKERS_DIR = REPO_ROOT / "workers"
WORKER_TIMEOUT_SECONDS = 3600.0  # separation of a long track on CPU can take most of an hour


@dataclass(frozen=True)
class ModelChoice:
    worker: str  # folder under workers/
    model: str  # name that goes into cache keys
    params: dict[str, ParamValue] = field(default_factory=dict)


SEPARATOR = ModelChoice("separate_bsroformer", "bs-roformer-sw", {"device": "mps"})
TRACKER = ModelChoice("beats_beatthis", "beat-this-final0", {"device": "cpu"})
LV_CHORDIA = ModelChoice("chords_lvchordia", "lv-chordia-full", {"dictionary": "full"})
BTC = ModelChoice("chords_btc", "btc-large-voca", {"device": "cpu"})

# No horn models run on this computer: no public sax weights, and the 53-stem model
# needs 16 GB of VRAM. Horns stay in the residue stem.
CAPABILITIES = Capabilities(sax_model=False, multi_stem=False, text_prompted=False)
