import json
import sys
import textwrap

import pytest

from jca_pipeline.contract import REQUEST_FILE, RESULT_FILE, WorkerRequest
from jca_pipeline.runner import (
    LOG_FILE,
    SubprocessRunner,
    WorkerFailed,
    python_command,
    uv_command,
)

OK_WORKER = """
import json, sys
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text())
out = Path(request["output_dir"])
(out / "chords.json").write_text("[]")
print("model says hello")
result = {"worker": request["worker"], "status": "ok", "outputs": {"chords": "chords.json"},
          "seconds": 0.1, "peak_memory_bytes": 1000, "device": "cpu",
          "versions": {"model": request["params"]["version"]}}
(out / "result.json").write_text(json.dumps(result))
"""

ERROR_WORKER = """
import json, sys
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text())
out = Path(request["output_dir"])
result = {"worker": request["worker"], "status": "error", "error": "model exploded",
          "seconds": 0.1, "peak_memory_bytes": 1000, "device": "cpu"}
(out / "result.json").write_text(json.dumps(result))
sys.exit(1)
"""

CRASH_WORKER = """
import sys
print("Traceback: something broke", file=sys.stderr)
sys.exit(3)
"""

SILENT_WORKER = "pass\n"

SLOW_WORKER = "import time\ntime.sleep(5)\n"

MISSING_OUTPUT_WORKER = """
import json, sys
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text())
out = Path(request["output_dir"])
result = {"worker": request["worker"], "status": "ok", "outputs": {"chords": "chords.json"},
          "seconds": 0.1, "peak_memory_bytes": 1000, "device": "cpu"}
(out / "result.json").write_text(json.dumps(result))
"""


def make_runner(tmp_path, source: str, timeout: float = 30.0) -> SubprocessRunner:
    worker_dir = tmp_path / "workers" / "fake"
    worker_dir.mkdir(parents=True)
    (worker_dir / "worker.py").write_text(textwrap.dedent(source), encoding="utf-8")
    return SubprocessRunner(
        workers_dir=tmp_path / "workers", timeout_seconds=timeout, command=python_command
    )


def request_for(tmp_path) -> WorkerRequest:
    return WorkerRequest(
        worker="fake",
        inputs={"audio": str(tmp_path / "mix.wav")},
        params={"version": "1.0"},
        output_dir=str(tmp_path / "out"),
    )


def test_a_successful_worker_returns_its_result(tmp_path):
    result = make_runner(tmp_path, OK_WORKER).run(request_for(tmp_path))
    out = tmp_path / "out"
    assert result.status == "ok"
    assert result.versions == {"model": "1.0"}
    assert (out / "chords.json").read_text() == "[]"
    assert json.loads((out / REQUEST_FILE).read_text())["worker"] == "fake"
    assert "model says hello" in (out / LOG_FILE).read_text()


def test_an_error_result_raises_with_its_message(tmp_path):
    with pytest.raises(WorkerFailed, match="fake: model exploded"):
        make_runner(tmp_path, ERROR_WORKER).run(request_for(tmp_path))


def test_a_crash_raises_with_the_log_tail(tmp_path):
    with pytest.raises(WorkerFailed, match="exit code 3") as caught:
        make_runner(tmp_path, CRASH_WORKER).run(request_for(tmp_path))
    assert "Traceback: something broke" in caught.value.log_tail


def test_a_worker_that_writes_no_result_raises(tmp_path):
    with pytest.raises(WorkerFailed, match="wrote no result.json"):
        make_runner(tmp_path, SILENT_WORKER).run(request_for(tmp_path))


def test_a_worker_that_runs_too_long_raises(tmp_path):
    with pytest.raises(WorkerFailed, match="timed out after 0.5 s"):
        make_runner(tmp_path, SLOW_WORKER, timeout=0.5).run(request_for(tmp_path))


def test_an_output_named_in_the_result_must_exist(tmp_path):
    with pytest.raises(WorkerFailed, match="chords.json.*missing"):
        make_runner(tmp_path, MISSING_OUTPUT_WORKER).run(request_for(tmp_path))


def test_an_invalid_result_file_raises(tmp_path):
    runner = make_runner(
        tmp_path,
        "import sys, json\nfrom pathlib import Path\n"
        "r = json.loads(Path(sys.argv[1]).read_text())\n"
        "(Path(r['output_dir']) / 'result.json').write_text('{\"status\": \"ok\"}')\n",
    )
    with pytest.raises(WorkerFailed, match="invalid result.json"):
        runner.run(request_for(tmp_path))


def test_an_unknown_worker_raises(tmp_path):
    runner = make_runner(tmp_path, OK_WORKER)
    request = request_for(tmp_path).model_copy(update={"worker": "missing"})
    with pytest.raises(WorkerFailed, match="no worker named 'missing'"):
        runner.run(request)


def test_the_result_file_is_removed_before_a_run(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / RESULT_FILE).write_text("stale", encoding="utf-8")
    with pytest.raises(WorkerFailed, match="wrote no result.json"):
        make_runner(tmp_path, SILENT_WORKER).run(request_for(tmp_path))


def test_uv_command_runs_the_worker_in_its_own_environment(tmp_path):
    command = uv_command(tmp_path / "workers" / "chords_btc", tmp_path / "request.json")
    assert command[:4] == ["uv", "run", "--directory", str(tmp_path / "workers" / "chords_btc")]
    assert command[4:] == ["python", "worker.py", str(tmp_path / "request.json")]


def test_python_command_uses_the_current_interpreter(tmp_path):
    command = python_command(tmp_path / "w", tmp_path / "request.json")
    assert command == [
        sys.executable,
        str(tmp_path / "w" / "worker.py"),
        str(tmp_path / "request.json"),
    ]
