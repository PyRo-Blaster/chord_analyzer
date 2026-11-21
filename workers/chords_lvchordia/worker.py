"""Worker: lv-chordia chord recognition.

Inputs: audio. Params: dictionary ("full", "submission" or "ismir2017").
Outputs: chords (raw lv-chordia JSON: start_time, end_time, chord).
"""

# --- worker contract (identical in every worker; generated from workers/_template) ----------
import json
import resource
import sys
import time
import traceback
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGES = ("lv-chordia", "torch", "librosa", "numpy")


def run(inputs: dict, params: dict, out: Path) -> dict[str, str]:
    from lv_chordia.chord_recognition import chord_recognition

    segments = chord_recognition(
        audio_path=inputs["audio"], chord_dict_name=str(params.get("dictionary", "full"))
    )
    (out / "chords.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
    return {"chords": "chords.json"}


RESULT_FILE = "result.json"


def _peak_memory_bytes() -> int:
    scale = 1 if sys.platform == "darwin" else 1024  # ru_maxrss is bytes on macOS, KiB on Linux
    self_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    children_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return max(self_peak, children_peak) * scale


def _versions(packages: tuple[str, ...]) -> dict[str, str]:
    found = {}
    for package in packages:
        try:
            found[package] = version(package)
        except PackageNotFoundError:
            found[package] = "not installed"
    return found


def _write_result(out: Path, request: dict, started: float, **fields: object) -> None:
    result = {
        "protocol": 1,
        "worker": request["worker"],
        "seconds": round(time.monotonic() - started, 3),
        "peak_memory_bytes": _peak_memory_bytes(),
        "versions": _versions(PACKAGES),
        **fields,
    }
    (out / RESULT_FILE).write_text(json.dumps(result, indent=2), encoding="utf-8")


def main(request_path: str) -> int:
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    out = Path(request["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    device = str(request.get("params", {}).get("device", "cpu"))
    try:
        outputs = run(request["inputs"], request.get("params", {}), out)
    except Exception as error:  # noqa: BLE001 - every failure is reported in result.json
        traceback.print_exc()
        _write_result(
            out, request, started, status="error", device=device,
            error=f"{type(error).__name__}: {error}",
        )  # fmt: skip
        return 1
    _write_result(out, request, started, status="ok", device=device, outputs=outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
