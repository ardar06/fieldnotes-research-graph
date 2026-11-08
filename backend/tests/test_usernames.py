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


def create_case_and_person(client):
    case = client.post("/api/cases", json={"title": "Username checks", "purpose": "Test"}).json()
    person = client.post(f"/api/cases/{case['id']}/people", json={"name": "Taylor Sample"}).json()
    return case["id"], person["id"]


def test_person_can_save_multiple_investigation_local_usernames(client):
    case_id, person_id = create_case_and_person(client)
    added = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames",
        json={"usernames": ["taylor.sample", "tsample_7"]},
    )
    assert added.status_code == 201, added.text
    assert [item["username"] for item in added.json()] == ["taylor.sample", "tsample_7"]

    listed = client.get(f"/api/cases/{case_id}/people/{person_id}/usernames")
    assert [item["username"] for item in listed.json()] == ["taylor.sample", "tsample_7"]

    duplicate = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames",
        json={"usernames": ["third", "taylor.sample"]},
    )
    assert duplicate.status_code == 409
    assert [item["username"] for item in client.get(f"/api/cases/{case_id}/people/{person_id}/usernames").json()] == ["taylor.sample", "tsample_7"]


def test_username_validation_rejects_patterns_and_invalid_characters(client):
    case_id, person_id = create_case_and_person(client)
    response = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames",
        json={"usernames": ["user{?}", "../other"]},
    )
    assert response.status_code == 422
    assert client.get(f"/api/cases/{case_id}/people/{person_id}/usernames").json() == []


def test_search_saves_bounded_unverified_results_without_response_bodies(client, monkeypatch):
    case_id, person_id = create_case_and_person(client)
    handle = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames",
        json={"usernames": ["taylor.sample"]},
    ).json()[0]

    sites = client.get("/api/username/sites").json()
    site_names = {site["name"] for site in sites}
    assert "GitHub" in site_names
    assert not any("Porn" in site["name"] for site in sites)
    second_site = next(name for name in site_names if name != "GitHub")

    calls = []

    async def fake_checks(username, requested_sites):
        calls.append((username, requested_sites))
        return [
            {
                "site_name": site_name,
                "profile_url": f"https://example.org/{site_name}/{username}",
                "status": "candidate" if index == 0 else "inconclusive",
                "http_status": 200 if index == 0 else 403,
            }
            for index, site_name in enumerate(requested_sites)
        ]

    monkeypatch.setattr("app.main.run_username_checks", fake_checks)

    no_confirmation = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames/{handle['id']}/search",
        json={"site_names": ["GitHub"], "confirm_authorized": False},
    )
    assert no_confirmation.status_code == 422
    assert calls == []

    checked = client.post(
        f"/api/cases/{case_id}/people/{person_id}/usernames/{handle['id']}/search",
        json={"site_names": ["GitHub", second_site], "confirm_authorized": True},
    )
    assert checked.status_code == 200, checked.text
    data = checked.json()
    assert data["username"] == "taylor.sample"
    assert calls == [("taylor.sample", ["GitHub", second_site])]
    assert [result["status"] for result in data["results"]] == ["candidate", "inconclusive"]
    assert all("response_text" not in result for result in data["results"])
    assert data["results"][0]["profile_url"] == "https://example.org/GitHub/taylor.sample"
    history = client.get(f"/api/cases/{case_id}/people/{person_id}/usernames/{handle['id']}/searches")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == data["id"]
