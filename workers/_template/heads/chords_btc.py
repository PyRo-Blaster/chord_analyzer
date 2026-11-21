"""Worker: BTC chord recognition, large vocabulary.

Inputs: audio. Params: device ("cpu" is faster than "mps" for this model).
Outputs: chords (raw BTC JSON: start, end, chord).
"""

PACKAGES = ("transformers", "torch", "librosa", "numpy")
REPOSITORY = "puar-playground/btc-chord"
# trust_remote_code runs code from the repository, so the commit is pinned. The code at
# this commit was read before it was first run (Phase 0).
REVISION = "d436f2f664f5107cd987774279b8ce171846e376"


def run(inputs: dict, params: dict, out: Path) -> dict[str, str]:
    from transformers import AutoModel

    model = AutoModel.from_pretrained(
        REPOSITORY, revision=REVISION, trust_remote_code=True,
        device=str(params.get("device", "cpu")),
    )  # fmt: skip
    segments = model.predict(inputs["audio"])
    (out / "chords.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
    return {"chords": "chords.json"}
