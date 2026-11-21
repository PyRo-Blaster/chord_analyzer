import pytest

from jca_pipeline.state import (
    STAGES,
    RunState,
    StageFailure,
    StageRecord,
    StateError,
    WorkerMetric,
    load_state,
    reusable,
    save_state,
    with_failure,
    with_record,
)

SHA = "a" * 64


def record(stage: str, key: str = "k1", outputs: dict | None = None) -> StageRecord:
    return StageRecord(stage=stage, key=key, outputs=outputs or {}, seconds=1.0)


def test_stage_order_matches_the_design():
    assert STAGES == ("uploaded", "separating", "tracking", "recognising", "decoded")


def test_records_are_kept_in_stage_order():
    state = with_record(
        with_record(RunState(track_sha256=SHA), record("tracking")), record("uploaded")
    )
    assert [r.stage for r in state.stages] == ["uploaded", "tracking"]


def test_a_new_record_replaces_the_old_one_for_its_stage():
    state = with_record(RunState(track_sha256=SHA), record("tracking", "old"))
    state = with_record(state, record("tracking", "new"))
    assert state.record("tracking").key == "new"
    assert len(state.stages) == 1


def test_with_record_does_not_change_the_old_state():
    before = RunState(track_sha256=SHA)
    with_record(before, record("uploaded"))
    assert before.stages == ()


def test_a_failure_is_cleared_when_its_stage_succeeds():
    failed = with_failure(RunState(track_sha256=SHA), StageFailure(stage="tracking", error="boom"))
    assert failed.failure.error == "boom"
    assert with_record(failed, record("tracking")).failure is None


def test_a_success_in_another_stage_keeps_the_failure():
    failed = with_failure(RunState(track_sha256=SHA), StageFailure(stage="tracking", error="boom"))
    assert with_record(failed, record("uploaded")).failure is not None


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        record("mixing")


def test_save_and_load_round_trip(tmp_path):
    metric = WorkerMetric(worker="chords_btc", seconds=7.0, peak_memory_bytes=10, device="cpu")
    state = with_record(
        RunState(track_sha256=SHA),
        StageRecord(stage="recognising", key="k", outputs={}, seconds=8.0, workers=(metric,)),
    )
    path = save_state(tmp_path / "run" / "state.json", state)
    assert load_state(path) == state
    assert not list(path.parent.glob("*.tmp"))


def test_load_of_a_missing_file_is_none(tmp_path):
    assert load_state(tmp_path / "state.json") is None


def test_load_of_a_broken_file_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StateError, match="state.json"):
        load_state(path)


def test_reusable_needs_the_same_key_and_the_files(tmp_path):
    output = tmp_path / "beats.json"
    output.write_text("{}", encoding="utf-8")
    state = with_record(
        RunState(track_sha256=SHA), record("tracking", "k1", {"beats": str(output)})
    )
    assert reusable(state, "tracking", "k1") == state.record("tracking")
    assert reusable(state, "tracking", "k2") is None
    assert reusable(state, "decoded", "k1") is None
    assert reusable(None, "tracking", "k1") is None
    output.unlink()
    assert reusable(state, "tracking", "k1") is None
