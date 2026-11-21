"""Worker: lv-chordia chord recognition.

Inputs: audio. Params: dictionary ("full", "submission" or "ismir2017").
Outputs: chords (raw lv-chordia JSON: start_time, end_time, chord).
"""

PACKAGES = ("lv-chordia", "torch", "librosa", "numpy")


def run(inputs: dict, params: dict, out: Path) -> dict[str, str]:
    from lv_chordia.chord_recognition import chord_recognition

    segments = chord_recognition(
        audio_path=inputs["audio"], chord_dict_name=str(params.get("dictionary", "full"))
    )
    (out / "chords.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
    return {"chords": "chords.json"}
