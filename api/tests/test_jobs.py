import threading

import pytest

from jca_api.jobs import Job, JobNotFound, JobOptions, JobRepository


def new_job(repository: JobRepository, filename: str = "take.flac") -> Job:
    return repository.create(
        filename=filename,
        audio_path=f"/data/uploads/{filename}",
        options=JobOptions(instruments=["piano", "double bass", "drums"]),
    )


@pytest.fixture
def repository(tmp_path):
    return JobRepository(tmp_path / "jobs.sqlite3")


def test_a_new_job_is_queued(repository):
    job = new_job(repository)
    assert job.status == "queued"
    assert job.finished_stages == ()
    assert len(job.id) == 32
    assert repository.get(job.id) == job


def test_unknown_job_raises(repository):
    with pytest.raises(JobNotFound, match="no-such-id"):
        repository.get("no-such-id")


def test_jobs_are_listed_newest_first(repository):
    first = new_job(repository, "a.flac")
    second = new_job(repository, "b.flac")
    assert [job.id for job in repository.recent()] == [second.id, first.id]


def test_next_queued_is_the_oldest_waiting_job(repository):
    first = new_job(repository, "a.flac")
    new_job(repository, "b.flac")
    assert repository.next_queued().id == first.id
    repository.mark_running(first.id, run_dir="/runs/abc")
    assert repository.next_queued().filename == "b.flac"


def test_a_job_moves_through_its_stages(repository):
    job = new_job(repository)
    running = repository.mark_running(job.id, run_dir="/runs/abc")
    assert (running.status, running.run_dir) == ("running", "/runs/abc")
    repository.add_finished_stage(job.id, "uploaded")
    after = repository.add_finished_stage(job.id, "separating")
    assert after.finished_stages == ("uploaded", "separating")
    done = repository.mark_done(job.id, warnings=["trumpet stays in the residue"])
    assert (done.status, done.warnings) == ("done", ("trumpet stays in the residue",))


def test_a_finished_stage_is_recorded_once(repository):
    job = new_job(repository)
    repository.add_finished_stage(job.id, "uploaded")
    assert repository.add_finished_stage(job.id, "uploaded").finished_stages == ("uploaded",)


def test_a_failed_job_keeps_its_error(repository):
    job = new_job(repository)
    failed = repository.mark_failed(job.id, "separating failed: out of memory")
    assert (failed.status, failed.error) == ("failed", "separating failed: out of memory")


def test_running_jobs_left_by_a_crash_go_back_in_the_queue(repository):
    job = new_job(repository)
    repository.mark_running(job.id, run_dir="/runs/abc")
    assert repository.requeue_running() == 1
    assert repository.get(job.id).status == "queued"


def test_options_round_trip(repository):
    options = JobOptions(
        instruments=["piano", "trumpet"], horn_counts={"trumpet": 2}, other=["organ"],
        beats_per_bar=3,
    )  # fmt: skip
    job = repository.create(filename="a.wav", audio_path="/a.wav", options=options)
    assert repository.get(job.id).options == options


def test_the_repository_works_from_several_threads(repository):
    errors = []

    def create_some():
        try:
            for _ in range(10):
                new_job(repository)
        except Exception as error:  # noqa: BLE001 - collected for the assertion below
            errors.append(error)

    threads = [threading.Thread(target=create_some) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(repository.recent(limit=100)) == 40


def test_edits_are_stored_by_beat_time_and_replace_earlier_ones(repository):
    from jca_core.chords.parts import ChordParts

    from jca_api.jobs import ChartEdit

    job = new_job(repository)
    d_minor = ChordParts.model_validate({"root": "D", "class": "min", "extensions": ["b7"]})
    g_seven = ChordParts.model_validate({"root": "G", "class": "dom7"})
    repository.save_edits(
        job.id, [ChartEdit(time=0.5, user_edit=d_minor), ChartEdit(time=1.0, user_edit=d_minor)]
    )
    saved = repository.save_edits(job.id, [ChartEdit(time=1.0, user_edit=g_seven)])
    assert [(edit.time, edit.user_edit.root) for edit in saved.edits] == [(0.5, "D"), (1.0, "G")]
    cleared = repository.save_edits(job.id, [ChartEdit(time=0.5, user_edit=None)])
    assert [edit.time for edit in cleared.edits] == [1.0]


def test_requeue_for_a_new_grid_keeps_the_stages_before_tracking(repository):
    job = new_job(repository)
    repository.mark_running(job.id, run_dir="/runs/abc")
    for stage in ("uploaded", "separating", "tracking", "recognising", "decoded"):
        repository.add_finished_stage(job.id, stage)
    repository.mark_done(job.id, warnings=[])
    options = job.options.model_copy(
        update={"beats_per_bar": 3, "tempo_bpm": 96.0, "first_beat_time": 0.2}
    )
    requeued = repository.requeue_with_options(job.id, options)
    assert requeued.status == "queued"
    assert requeued.finished_stages == ("uploaded", "separating")
    assert requeued.options.beats_per_bar == 3
    assert requeued.options.tempo_bpm == 96.0


def test_an_older_table_without_edits_is_migrated(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, filename TEXT NOT NULL,"
        " audio_path TEXT NOT NULL, options TEXT NOT NULL, status TEXT NOT NULL,"
        " finished_stages TEXT NOT NULL DEFAULT '[]', run_dir TEXT, error TEXT,"
        " warnings TEXT NOT NULL DEFAULT '[]')"
    )
    connection.execute(
        "INSERT INTO jobs (id, created_at, filename, audio_path, options, status)"
        " VALUES ('a', '2026-11-20', 'x.wav', '/x.wav', '{\"instruments\": [\"piano\"]}', 'done')"
    )
    connection.commit()
    connection.close()
    assert JobRepository(path).get("a").edits == ()
