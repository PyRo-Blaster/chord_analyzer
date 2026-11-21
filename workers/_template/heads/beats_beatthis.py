"""Worker: beat-this beat and downbeat tracking.

Inputs: audio. Params: device ("cpu" is faster than "mps" here), checkpoint (default final0).
Outputs: beats (JSON: beats, downbeats in seconds).
"""

PACKAGES = ("beat-this", "torch", "torchaudio", "soundfile")


def run(inputs: dict, params: dict, out: Path) -> dict[str, str]:
    from beat_this.inference import File2Beats

    tracker = File2Beats(
        checkpoint_path=str(params.get("checkpoint", "final0")),
        device=str(params.get("device", "cpu")),
        dbn=False,
    )
    beats, downbeats = tracker(inputs["audio"])
    marks = {"beats": [float(t) for t in beats], "downbeats": [float(t) for t in downbeats]}
    (out / "beats.json").write_text(json.dumps(marks, indent=2), encoding="utf-8")
    return {"beats": "beats.json"}
