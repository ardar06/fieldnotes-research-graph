import json
import stat

from fastapi.testclient import TestClient

from app.main import app


def test_ai_settings_saves_key_server_side_and_never_returns_it(tmp_path, monkeypatch):
    path = tmp_path / "private" / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(path))
    monkeypatch.setenv("AI_ENABLED", "false")
    client = TestClient(app)
    secret = "test-provider-key-do-not-return"

    response = client.put(
        "/api/ai/settings",
        json={
            "provider_name": "OpenCode Console",
            "base_url": "https://opencode.ai/inference/openai/v1",
            "model": "test-model",
            "api_key": secret,
            "enabled": True,
        },
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    assert secret not in response.text
    assert response.json()["api_key_configured"] is True
    assert response.json()["source"] == "local"
    assert client.get("/api/ai/status").json()["enabled"] is True
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["api_key"] == secret

    settings = client.get("/api/ai/settings")
    assert secret not in settings.text
    assert "api_key" not in settings.json()


def test_ai_settings_reject_cross_origin_and_non_https_remote(tmp_path, monkeypatch):
    path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(path))
    client = TestClient(app)
    payload = {
        "provider_name": "Provider",
        "base_url": "http://example.com/v1",
        "model": "model",
        "api_key": "private-test-key",
        "enabled": True,
    }
    cross_origin = client.put(
        "/api/ai/settings",
        json=payload,
        headers={"Origin": "https://attacker.invalid"},
    )
    assert cross_origin.status_code == 403
    assert not path.exists()

    insecure_endpoint = client.put(
        "/api/ai/settings",
        json=payload,
        headers={"Origin": "http://testserver"},
    )
    assert insecure_endpoint.status_code == 422
    assert not path.exists()


def test_clearing_local_ai_settings_removes_saved_key(tmp_path, monkeypatch):
    path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(path))
    client = TestClient(app)
    client.put(
        "/api/ai/settings",
        json={
            "provider_name": "Local provider",
            "base_url": "https://example.com/v1",
            "model": "model",
            "api_key": "private-test-key",
            "enabled": True,
        },
    )
    cleared = client.delete("/api/ai/settings", headers={"Origin": "http://testserver"})
    assert cleared.status_code == 200
    assert cleared.json()["source"] == "none"
    assert not path.exists()
    assert client.get("/api/ai/status").json()["enabled"] is False
