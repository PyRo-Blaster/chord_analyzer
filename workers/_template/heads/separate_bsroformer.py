"""Worker: BS-RoFormer SW six-stem separation.

Inputs: mix (a WAV file). Params: device ("mps", "cpu" or "cuda").
Outputs: vocals, drums, bass, guitar, piano, other (WAV files at the rate of the input).
"""

import shutil
import subprocess

PACKAGES = ("bs-roformer-infer", "torch", "numpy")
STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")
INPUT_NAME = "mix"


def run(inputs: dict, params: dict, out: Path) -> dict[str, str]:
    staging = out / "input"
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / f"{INPUT_NAME}.wav"
    staged.unlink(missing_ok=True)
    staged.symlink_to(Path(inputs["mix"]).resolve())
    command = [
        str(Path(sys.executable).parent / "bs-roformer-infer"),
        "--input_folder", str(staging),
        "--store_dir", str(out),
        "--device", str(params.get("device", "cpu")),
    ]  # fmt: skip
    subprocess.run(command, check=True)
    shutil.rmtree(staging)
    (out / f"{INPUT_NAME}_instrumental.wav").unlink(missing_ok=True)
    outputs = {stem: f"{INPUT_NAME}_{stem}.wav" for stem in STEMS}
    missing = [name for name in outputs.values() if not (out / name).is_file()]
    if missing:
        raise RuntimeError(f"the separator did not write {', '.join(missing)}")
    return outputs
