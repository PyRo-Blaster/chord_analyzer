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


@pytest.fixture
def done_track(client, service):
    track_id = upload(client, content=wav_bytes(8.0)).json()["data"]["id"]
    service.run_next()
    return track_id


@needs_ffmpeg
def test_chords_returns_the_beats_with_both_models_and_symbols(client, done_track):
    data = client.get(f"/api/tracks/{done_track}/chords").json()["data"]
    assert len(data["beats"]) == 16
    beat = data["beats"][0]
    assert beat["lv_chordia"]["symbol"] == "Cmaj7"
    assert beat["draft"]["tier1"] == "C maj"
    assert data["grid"] == {
        "beats_per_bar": None, "first_downbeat_index": None, "tempo_bpm": None, "first_beat_time": None,
    }  # fmt: skip


def test_chords_of_an_unfinished_track_get_a_409(client):
    track_id = upload(client).json()["data"]["id"]
    response = client.get(f"/api/tracks/{track_id}/chords")
    assert response.status_code == 409
    assert response.json()["error"] == "The chart is not ready yet"


@needs_ffmpeg
def test_patch_chart_saves_edits_and_returns_the_new_view(client, done_track):
    edit = {
        "time": 2.0,
        "user_edit": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
    }
    response = client.patch(f"/api/tracks/{done_track}/chart", json={"edits": [edit]})
    assert response.status_code == 200
    assert response.json()["data"]["beats"][4]["user_edit"]["symbol"] == "Dm7"
    again = client.get(f"/api/tracks/{done_track}/chords").json()["data"]
    assert again["beats"][4]["user_edit"]["symbol"] == "Dm7"
    cleared = client.patch(
        f"/api/tracks/{done_track}/chart", json={"edits": [{"time": 2.0, "user_edit": None}]}
    )
    assert cleared.json()["data"]["beats"][4]["user_edit"] is None


@needs_ffmpeg
@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"edits": [{"time": 2.3, "user_edit": None}]}, "no beat at 2.30 s"),
        ({"edits": [{"time": 0.0, "user_edit": {"root": "H", "class": None}}]}, "root 'H'"),
        ({"edits": []}, "edits"),
    ],
)
def test_patch_chart_rejects_bad_edits(client, done_track, body, message):
    response = client.patch(f"/api/tracks/{done_track}/chart", json=body)
    assert response.status_code == 400
    assert message in response.json()["error"]


@needs_ffmpeg
def test_patch_grid_requeues_the_track_with_the_new_grid(client, service, done_track):
    response = client.patch(
        f"/api/tracks/{done_track}/grid", json={"beats_per_bar": 3, "first_downbeat_index": 1}
    )
    assert response.status_code == 202
    track = response.json()["data"]
    assert track["status"] == "queued"
    assert [stage["state"] for stage in track["stages"]][:3] == ["done", "done", "waiting"]
    service.run_next()
    data = client.get(f"/api/tracks/{done_track}/chords").json()["data"]
    assert data["grid"]["beats_per_bar"] == 3
    assert [(beat["bar"], beat["beat"]) for beat in data["beats"][:5]] == [
        (0, 1), (1, 1), (1, 2), (1, 3), (2, 1),
    ]  # fmt: skip


@needs_ffmpeg
def test_patch_grid_with_a_tapped_tempo(client, service, done_track):
    body = {"beats_per_bar": 4, "tempo_bpm": 100.0, "first_beat_time": 0.3}
    assert client.patch(f"/api/tracks/{done_track}/grid", json=body).status_code == 202
    service.run_next()
    beats = client.get(f"/api/tracks/{done_track}/chords").json()["data"]["beats"]
    assert [beat["time"] for beat in beats[:2]] == [0.3, 0.9]


@needs_ffmpeg
def test_patch_grid_rejects_a_half_tapped_tempo(client, done_track):
    response = client.patch(f"/api/tracks/{done_track}/grid", json={"tempo_bpm": 100.0})
    assert response.status_code == 400
    assert "first_beat_time" in response.json()["error"]


def test_patch_grid_waits_for_a_running_job(client, service):
    track_id = upload(client).json()["data"]["id"]
    response = client.patch(f"/api/tracks/{track_id}/grid", json={"beats_per_bar": 3})
    assert response.status_code == 409
    assert "wait" in response.json()["error"]


@needs_ffmpeg
def test_evidence_for_each_source(client, done_track):
    data = client.get(f"/api/tracks/{done_track}/evidence", params={"source": "bass"}).json()[
        "data"
    ]
    assert data["source"] == "bass"
    assert len(data["profiles"]) == 16 and len(data["profiles"][0]) == 12
    bad = client.get(f"/api/tracks/{done_track}/evidence", params={"source": "trumpet"})
    assert bad.status_code == 400


@needs_ffmpeg
def test_exports(client, done_track):
    text = client.get(f"/api/tracks/{done_track}/export", params={"format": "text"})
    assert text.headers["content-type"].startswith("text/plain")
    assert 'filename="take-chart.txt"' in text.headers["content-disposition"]
    assert text.text == "| Cmaj7 | Cmaj7 | Cmaj7 | Cmaj7 |\n"
    document = client.get(f"/api/tracks/{done_track}/export", params={"format": "json"})
    assert 'filename="take-analysis.json"' in document.headers["content-disposition"]
    assert document.json()["schema_version"] == 1
    stems = client.get(f"/api/tracks/{done_track}/export", params={"format": "stems"})
    assert stems.headers["content-type"] == "application/zip"
    assert 'filename="take-stems.zip"' in stems.headers["content-disposition"]
    assert stems.content[:2] == b"PK"
    assert (
        client.get(f"/api/tracks/{done_track}/export", params={"format": "pdf"}).status_code == 400
    )
