import io
import json
import shutil

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from jca_api.app import create_app
from jca_api.config import Settings
from jca_api.fake_runner import FakeModelRunner
from jca_api.jobs import JobRepository
from jca_api.service import JobService, analyze_with

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
TRIO = {"instruments": ["piano", "double bass", "drums"]}


def wav_bytes(seconds: float = 4.0, rate: int = 44100) -> bytes:
    tone = 0.2 * np.sin(2 * np.pi * 220 * np.arange(int(seconds * rate)) / rate)
    buffer = io.BytesIO()
    sf.write(buffer, np.column_stack([tone, tone]), rate, format="WAV")
    return buffer.getvalue()


@pytest.fixture
def service(tmp_path):
    settings = Settings(data_dir=tmp_path / "data")
    return JobService(
        JobRepository(settings.database_path),
        settings.data_dir,
        analyze_with(FakeModelRunner(delay_seconds=0)),
        settings.max_upload_bytes,
    )


@pytest.fixture
def client(tmp_path, service):
    app = create_app(Settings(data_dir=tmp_path / "data"), service=service, start_worker=False)
    with TestClient(app) as test_client:
        yield test_client


def upload(client, options=TRIO, filename="take.wav", content=None):
    files = {"file": (filename, content if content is not None else wav_bytes(), "audio/wav")}
    return client.post("/api/tracks", files=files, data={"options": json.dumps(options)})


def test_instruments_and_presets(client):
    body = client.get("/api/instruments").json()
    assert body["success"] is True and body["error"] is None
    data = body["data"]
    assert "double bass" in data["instruments"]
    assert "trumpet" in data["horns"] and "piano" not in data["horns"]
    presets = {preset["id"]: preset for preset in data["presets"]}
    assert list(presets) == ["piano-trio", "quartet-one-horn", "quintet-two-horns", "big-band"]
    assert presets["piano-trio"]["instruments"] == ["piano", "double bass", "drums"]
    assert presets["big-band"]["horn_counts"]["trumpet"] == 4


def test_upload_queues_a_track(client):
    response = upload(client)
    assert response.status_code == 201
    track = response.json()["data"]
    assert track["status"] == "queued"
    assert track["progress"] == 0
    assert [stage["state"] for stage in track["stages"]] == ["waiting"] * 5
    assert track["stems"] == []


@pytest.mark.parametrize(
    ("options", "filename", "message"),
    [
        (TRIO, "take.ogg", "MP3, WAV, FLAC or M4A"),
        ({"instruments": ["banjo"]}, "take.wav", "Unknown instrument 'banjo'"),
        ({"instruments": []}, "take.wav", "instruments"),
    ],
)
def test_invalid_uploads_get_a_clear_400(client, options, filename, message):
    response = upload(client, options=options, filename=filename)
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False and body["data"] is None
    assert message in body["error"]


def test_options_that_are_not_json_get_a_400(client):
    files = {"file": ("take.wav", wav_bytes(), "audio/wav")}
    response = client.post("/api/tracks", files=files, data={"options": "{not json"})
    assert response.status_code == 400
    assert "options" in response.json()["error"]


def test_a_missing_file_field_gets_a_400(client):
    response = client.post("/api/tracks", data={"options": json.dumps(TRIO)})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_an_unknown_track_gets_a_404(client):
    response = client.get("/api/tracks/nope")
    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "error": "There is no track with id 'nope'",
    }


@needs_ffmpeg
def test_a_finished_track_lists_its_stems_and_serves_them(client, service):
    track_id = upload(client).json()["data"]["id"]
    service.run_next()
    track = client.get(f"/api/tracks/{track_id}").json()["data"]
    assert track["status"] == "done"
    assert track["progress"] == 1
    assert {stage["state"] for stage in track["stages"]} == {"done"}
    assert [(stem["name"], stem["kind"]) for stem in track["stems"]] == [
        ("drums", "stem"), ("double bass", "stem"), ("piano", "stem"), ("residue", "residue"),
    ]  # fmt: skip
    url = track["stems"][1]["url"]
    assert url == f"/api/tracks/{track_id}/stems/double%20bass"
    audio = client.get(url)
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/flac"
    assert sf.info(io.BytesIO(audio.content)).samplerate == 44100
    download = client.get(url, params={"download": "1"})
    assert 'attachment; filename="take-double_bass.flac"' in download.headers["content-disposition"]


@needs_ffmpeg
def test_stems_support_range_requests(client, service):
    track_id = upload(client).json()["data"]["id"]
    service.run_next()
    response = client.get(f"/api/tracks/{track_id}/stems/piano", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert len(response.content) == 100


@needs_ffmpeg
def test_an_unknown_stem_gets_a_404(client, service):
    track_id = upload(client).json()["data"]["id"]
    service.run_next()
    response = client.get(f"/api/tracks/{track_id}/stems/trumpet")
    assert response.status_code == 404
    assert "trumpet" in response.json()["error"]


def test_a_running_track_shows_its_current_stage(client, service):
    track_id = upload(client).json()["data"]["id"]
    service.repository.mark_running(track_id, run_dir="/nowhere")
    service.repository.add_finished_stage(track_id, "uploaded")
    track = client.get(f"/api/tracks/{track_id}").json()["data"]
    assert [stage["state"] for stage in track["stages"]] == [
        "done", "running", "waiting", "waiting", "waiting",
    ]  # fmt: skip
    assert track["progress"] == 0.2


def test_a_failed_track_shows_the_failed_stage_and_error(client, service):
    track_id = upload(client).json()["data"]["id"]
    service.repository.add_finished_stage(track_id, "uploaded")
    service.repository.mark_failed(track_id, "separating failed: out of memory")
    track = client.get(f"/api/tracks/{track_id}").json()["data"]
    assert track["stages"][1]["state"] == "failed"
    assert track["error"] == "separating failed: out of memory"


def test_tracks_are_listed_newest_first(client):
    first = upload(client).json()["data"]["id"]
    second = upload(client).json()["data"]["id"]
    listed = [track["id"] for track in client.get("/api/tracks").json()["data"]]
    assert listed == [second, first]


def test_the_app_starts_and_stops_its_worker(tmp_path, service):
    app = create_app(Settings(data_dir=tmp_path / "data"), service=service, start_worker=True)
    with TestClient(app) as test_client:
        assert test_client.get("/api/instruments").status_code == 200
        assert app.state.worker.is_alive()
    assert not app.state.worker.is_alive()
