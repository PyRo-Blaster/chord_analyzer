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
