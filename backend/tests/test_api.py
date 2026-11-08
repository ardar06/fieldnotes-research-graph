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


def test_research_graph_keeps_claims_linked_to_sources(client):
    case_response = client.post(
        "/api/cases", json={"title": "Demo investigation", "purpose": "Journalism"}
    )
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    person_a = client.post(
        f"/api/cases/{case_id}/people", json={"name": "Avery Example"}
    ).json()
    person_b = client.post(
        f"/api/cases/{case_id}/people", json={"name": "Jordan Sample"}
    ).json()
    source = client.post(
        f"/api/cases/{case_id}/sources",
        json={
            "url": "https://newsroom.example/story/42",
            "title": "Public meeting report",
            "retrieved_on": "2026-11-06",
        },
    ).json()

    finding = client.post(
        f"/api/cases/{case_id}/findings",
        json={
            "person_id": person_a["id"],
            "source_id": source["id"],
            "claim": "Was listed as a speaker at the public meeting",
            "confidence": 0.8,
        },
    )
    assert finding.status_code == 201, finding.text

    relationship = client.post(
        f"/api/cases/{case_id}/relationships",
        json={
            "source_person_id": person_a["id"],
            "target_person_id": person_b["id"],
            "source_id": source["id"],
            "label": "Appeared together in public reporting",
            "confidence": 0.65,
        },
    )
    assert relationship.status_code == 201, relationship.text

    graph = client.get(f"/api/cases/{case_id}/graph")
    assert graph.status_code == 200
    payload = graph.json()
    assert {node["name"] for node in payload["nodes"]} == {
        "Avery Example",
        "Jordan Sample",
    }
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["source_title"] == "Public meeting report"
    assert payload["edges"][0]["confidence"] == pytest.approx(0.65)
    assert payload["findings_count"] == 1


def test_sources_only_allow_http_or_https_urls(client):
    case_id = client.post(
        "/api/cases", json={"title": "URL validation", "purpose": "Research"}
    ).json()["id"]
    response = client.post(
        f"/api/cases/{case_id}/sources",
        json={"url": "file:///etc/passwd", "title": "Not a web source"},
    )
    assert response.status_code == 422


def test_finding_cannot_reference_a_person_from_another_case(client):
    case_one = client.post(
        "/api/cases", json={"title": "Case one", "purpose": "Research"}
    ).json()["id"]
    case_two = client.post(
        "/api/cases", json={"title": "Case two", "purpose": "Research"}
    ).json()["id"]
    person = client.post(
        f"/api/cases/{case_one}/people", json={"name": "Case-one person"}
    ).json()
    source = client.post(
        f"/api/cases/{case_two}/sources",
        json={"url": "https://example.org/source", "title": "Public source"},
    ).json()

    response = client.post(
        f"/api/cases/{case_two}/findings",
        json={
            "person_id": person["id"],
            "source_id": source["id"],
            "claim": "This must not cross investigation boundaries",
        },
    )
    assert response.status_code == 404


def test_export_contains_provenance_and_user_can_delete_case(client):
    created = client.post(
        "/api/cases", json={"title": "Export case", "purpose": "Public interest"}
    )
    case_id = created.json()["id"]
    person = client.post(
        f"/api/cases/{case_id}/people", json={"name": "Taylor Sample"}
    ).json()
    source = client.post(
        f"/api/cases/{case_id}/sources",
        json={"url": "https://example.org/source", "title": "Reference"},
    ).json()
    client.post(
        f"/api/cases/{case_id}/findings",
        json={"person_id": person["id"], "source_id": source["id"], "claim": "A sourced note"},
    )

    export_response = client.get(f"/api/cases/{case_id}/export")
    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["people"][0]["name"] == "Taylor Sample"
    assert exported["findings"][0]["source"]["url"] == "https://example.org/source"

    deleted = client.delete(f"/api/cases/{case_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/cases/{case_id}/export").status_code == 404
