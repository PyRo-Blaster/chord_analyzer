import pytest

from jca_api.config import DEFAULT_MAX_UPLOAD_MB, Settings
from jca_api.serve import main


def test_defaults(monkeypatch):
    for name in ("JCA_DATA_DIR", "JCA_MAX_UPLOAD_MB", "JCA_FAKE_PIPELINE", "JCA_POLL_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.max_upload_mb == DEFAULT_MAX_UPLOAD_MB
    assert settings.fake_pipeline is False
    assert settings.database_path.name == "jobs.sqlite3"


def test_settings_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("JCA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JCA_MAX_UPLOAD_MB", "2")
    monkeypatch.setenv("JCA_FAKE_PIPELINE", "1")
    settings = Settings.from_env()
    assert (settings.data_dir, settings.max_upload_bytes) == (tmp_path, 2 * 1024 * 1024)
    assert settings.fake_pipeline is True


def test_an_invalid_limit_is_rejected(monkeypatch):
    monkeypatch.setenv("JCA_MAX_UPLOAD_MB", "0")
    with pytest.raises(ValueError, match="at least 1"):
        Settings.from_env()


def test_serve_reports_bad_settings(monkeypatch, capsys):
    monkeypatch.setenv("JCA_MAX_UPLOAD_MB", "0")
    assert main([]) == 1
    assert "JCA_MAX_UPLOAD_MB" in capsys.readouterr().err


def test_serve_starts_uvicorn_with_the_app(monkeypatch, tmp_path):
    monkeypatch.setenv("JCA_DATA_DIR", str(tmp_path))
    started = {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: started.update(host=host, port=port))
    assert main(["--port", "8123"]) == 0
    assert started == {"host": "127.0.0.1", "port": 8123}
