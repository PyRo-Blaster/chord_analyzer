import pytest
from pydantic import ValidationError

from jca_pipeline.contract import (
    PROTOCOL_VERSION,
    REQUEST_FILE,
    RESULT_FILE,
    WorkerRequest,
    WorkerResult,
)


def ok_result(**fields) -> WorkerResult:
    base = {
        "worker": "chords_btc",
        "status": "ok",
        "outputs": {"chords": "chords.json"},
        "seconds": 7.2,
        "peak_memory_bytes": 700_000_000,
        "device": "cpu",
    }
    return WorkerResult.model_validate({**base, **fields})


def test_file_names_and_version():
    assert (REQUEST_FILE, RESULT_FILE, PROTOCOL_VERSION) == ("request.json", "result.json", 1)


def test_request_round_trips_through_json():
    request = WorkerRequest(
        worker="chords_lvchordia",
        inputs={"audio": "/tmp/mix.wav"},
        params={"dictionary": "full"},
        output_dir="/tmp/out",
    )
    assert WorkerRequest.model_validate_json(request.model_dump_json()) == request
    assert request.protocol == PROTOCOL_VERSION


def test_request_needs_a_worker_name():
    with pytest.raises(ValidationError):
        WorkerRequest(worker="", inputs={}, output_dir="/tmp/out")


def test_ok_result_with_outputs():
    result = ok_result()
    assert result.outputs == {"chords": "chords.json"}
    assert result.error is None


def test_ok_result_must_not_carry_an_error():
    with pytest.raises(ValidationError, match="ok result must not carry an error"):
        ok_result(error="boom")


def test_error_result_must_carry_an_error():
    with pytest.raises(ValidationError, match="error result must carry an error"):
        ok_result(status="error", outputs={})


def test_error_result():
    result = ok_result(status="error", outputs={}, error="model failed")
    assert result.error == "model failed"


@pytest.mark.parametrize("name", ["../escape.json", "/abs/path.json", "sub/dir.json", ""])
def test_output_names_must_be_plain_file_names(name):
    with pytest.raises(ValidationError, match="plain file name"):
        ok_result(outputs={"chords": name})


@pytest.mark.parametrize("fields", [{"seconds": -1.0}, {"peak_memory_bytes": -1}])
def test_metrics_cannot_be_negative(fields):
    with pytest.raises(ValidationError):
        ok_result(**fields)


def test_another_protocol_version_is_rejected():
    with pytest.raises(ValidationError):
        ok_result(protocol=2)
