import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def configure_ai(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER_NAME", "Test provider")
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_API_KEY", "test-secret-not-for-response")


def create_case_with_sources(client):
    case = client.post("/api/cases", json={"title": "AI test", "purpose": "Testing only"}).json()
    person = client.post(f"/api/cases/{case['id']}/people", json={"name": "Morgan Example"}).json()
    selected = client.post(
        f"/api/cases/{case['id']}/sources",
        json={"url": "https://example.org/reviewed", "title": "Reviewed public report", "publisher": "Example"},
    ).json()
    unrelated = client.post(
        f"/api/cases/{case['id']}/sources",
        json={"url": "https://example.org/unselected", "title": "Unselected report", "publisher": "Example"},
    ).json()
    client.post(
        f"/api/cases/{case['id']}/findings",
        json={
            "person_id": person["id"],
            "source_id": selected["id"],
            "claim": "The report lists Morgan as a panel speaker.",
            "excerpt": "Morgan Example spoke at the public panel on Tuesday.",
        },
    )
    client.post(
        f"/api/cases/{case['id']}/findings",
        json={
            "person_id": person["id"],
            "source_id": unrelated["id"],
            "claim": "Unselected material must not leave the app.",
            "excerpt": "PRIVATE_UNSELECTED_SENTINEL",
        },
    )
    return case, selected, unrelated


def test_ai_status_does_not_disclose_key_or_endpoint(client, monkeypatch):
    configure_ai(monkeypatch)
    response = client.get("/api/ai/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["provider_name"] == "Test provider"
    assert response.json()["model"] == "test-model"
    assert "test-secret-not-for-response" not in response.text
    assert "ai.example" not in response.text


def test_ai_analysis_requires_explicit_provider_consent(client, monkeypatch):
    configure_ai(monkeypatch)
    case, source, _ = create_case_with_sources(client)
    response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Summarize the excerpt.", "source_ids": [source["id"]], "confirm_provider_share": False},
    )
    assert response.status_code == 422


def test_ai_receives_only_selected_source_material_and_returns_verified_quote(client, monkeypatch):
    configure_ai(monkeypatch)
    case, selected, _ = create_case_with_sources(client)
    model_body = {
        "summary": "The selected report records a public panel appearance.",
        "claims": [
            {
                "text": "Morgan Example spoke at the public panel.",
                "source_ids": [selected["id"]],
                "evidence_quote": "Morgan Example spoke at the public panel on Tuesday.",
                "confidence": "medium",
            }
        ],
        "open_questions": ["What was the panel's subject?"],
    }
    captured = {}

    def fake_post(url, *, headers, json, timeout, follow_redirects):
        captured.update({"url": url, "headers": headers, "payload": json, "timeout": timeout, "follow_redirects": follow_redirects})
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json_module_dumps(model_body)}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Summarize the source-supported points.", "source_ids": [selected["id"]], "confirm_provider_share": True},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_name"] == "Test provider"
    assert payload["claims"][0]["quote_verified"] is True
    assert payload["claims"][0]["source_ids"] == [selected["id"]]
    assert payload["sources"][0]["url"] == "https://example.org/reviewed"
    assert "test-secret-not-for-response" not in response.text

    assert captured["url"] == "https://ai.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-secret-not-for-response"
    assert captured["follow_redirects"] is False
    messages = captured["payload"]["messages"]
    serialized = json.dumps(messages)
    assert "Morgan Example spoke at the public panel on Tuesday." in serialized
    assert "PRIVATE_UNSELECTED_SENTINEL" not in serialized
    assert "https://example.org/reviewed" not in serialized
    assert "tools" not in captured["payload"]
    assert len(client.get(f"/api/cases/{case['id']}/findings").json()) == 2


def json_module_dumps(value):
    return json.dumps(value)


def test_ai_marks_unverified_quotes_and_rejects_foreign_source_ids(client, monkeypatch):
    configure_ai(monkeypatch)
    case, selected, _ = create_case_with_sources(client)
    model_body = {
        "summary": "Possible association; check the original source.",
        "claims": [
            {
                "text": "A claim with an invented quotation.",
                "source_ids": [selected["id"]],
                "evidence_quote": "This exact sentence was not in the excerpt.",
                "confidence": "high",
            }
        ],
        "open_questions": [],
    }
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": json.dumps(model_body)}}]},
        ),
    )
    response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Review the excerpt.", "source_ids": [selected["id"]], "confirm_provider_share": True},
    )
    assert response.status_code == 200
    assert response.json()["claims"][0]["quote_verified"] is False

    other_case = client.post("/api/cases", json={"title": "Other", "purpose": "Testing"}).json()
    foreign_source = client.post(
        f"/api/cases/{other_case['id']}/sources",
        json={"url": "https://example.org/private", "title": "Foreign source"},
    ).json()
    foreign_response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Review.", "source_ids": [foreign_source["id"]], "confirm_provider_share": True},
    )
    assert foreign_response.status_code == 404


def test_disabled_ai_returns_no_provider_call(client, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    status = client.get("/api/ai/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    case, source, _ = create_case_with_sources(client)
    response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Analyze.", "source_ids": [source["id"]], "confirm_provider_share": True},
    )
    assert response.status_code == 503


def test_opencode_console_chat_completions_session_header_is_case_scoped(client, monkeypatch):
    configure_ai(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_NAME", "OpenCode Console")
    monkeypatch.setenv("AI_BASE_URL", "https://opencode.ai/inference/openai/v1")
    case, source, _ = create_case_with_sources(client)
    captured_headers = []

    def fake_post(url, **kwargs):
        captured_headers.append((url, kwargs["headers"]))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": json.dumps({"summary": "Reviewed.", "claims": [], "open_questions": []})}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    for _ in range(2):
        response = client.post(
            f"/api/cases/{case['id']}/ai/analyze",
            json={"question": "Summarize.", "source_ids": [source["id"]], "confirm_provider_share": True},
        )
        assert response.status_code == 200

    assert [url for url, _ in captured_headers] == [
        "https://opencode.ai/inference/openai/v1/chat/completions",
        "https://opencode.ai/inference/openai/v1/chat/completions",
    ]
    session_ids = [headers["x-opencode-session"] for _, headers in captured_headers]
    assert session_ids[0].startswith("ses_")
    assert session_ids[0] == session_ids[1]


@pytest.mark.parametrize("free_model", ["crouton-alpha-free", "big-pickle"])
def test_opencode_console_free_tier_model_is_blocked_before_provider_call(client, monkeypatch, free_model):
    configure_ai(monkeypatch)
    monkeypatch.setenv("AI_BASE_URL", "https://opencode.ai/inference/openai/v1")
    monkeypatch.setenv("AI_MODEL", free_model)
    calls = []

    def fail_if_called(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("free-tier model must be blocked before network call")

    monkeypatch.setattr(httpx, "post", fail_if_called)
    status = client.get("/api/ai/status").json()
    assert status["enabled"] is False
    assert "free-tier" in status["reason"].lower()
    case, source, _ = create_case_with_sources(client)
    response = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Summarize.", "source_ids": [source["id"]], "confirm_provider_share": True},
    )
    assert response.status_code == 503
    assert calls == []


def test_ai_provider_http_errors_are_actionable_but_hide_body_and_key(client, monkeypatch):
    configure_ai(monkeypatch)
    case, source, _ = create_case_with_sources(client)
    response_body_marker = "provider-body-private-marker"

    def fake_post(url, **_kwargs):
        response = httpx.Response(403, request=httpx.Request("POST", url), text=response_body_marker)
        raise httpx.HTTPStatusError("Forbidden", request=response.request, response=response)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = client.post(
        f"/api/cases/{case['id']}/ai/analyze",
        json={"question": "Summarize.", "source_ids": [source["id"]], "confirm_provider_share": True},
    )
    assert result.status_code == 502
    assert "HTTP 403" in result.json()["detail"]
    assert "access" in result.json()["detail"].lower()
    assert response_body_marker not in result.text
    assert "test-secret-not-for-response" not in result.text
