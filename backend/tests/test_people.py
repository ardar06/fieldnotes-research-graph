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


def create_case(client, title):
    response = client.post("/api/cases", json={"title": title, "purpose": "Test workspace"})
    assert response.status_code == 201
    return response.json()["id"]


def test_global_person_can_be_reused_without_sharing_case_notes(client):
    first_case = create_case(client, "First workspace")
    first = client.post(
        f"/api/cases/{first_case}/people",
        json={"name": "Alex Example", "aliases": ["A. Example"], "notes": "Notes for first case only"},
    )
    assert first.status_code == 201, first.text
    first_person = first.json()
    identity_id = first_person["identity_id"]
    assert identity_id

    global_search = client.get("/api/people", params={"q": "Alex"})
    assert global_search.status_code == 200
    assert len(global_search.json()) == 1
    assert global_search.json()[0]["id"] == identity_id
    assert global_search.json()[0]["canonical_name"] == "Alex Example"
    assert "notes" not in global_search.json()[0]
    assert "case_id" not in global_search.json()[0]

    second_case = create_case(client, "Second workspace")
    second = client.post(
        f"/api/cases/{second_case}/people",
        json={"name": "Alex Example", "identity_id": identity_id, "aliases": ["Alex E."], "notes": "Notes for second case only"},
    )
    assert second.status_code == 201, second.text
    second_person = second.json()
    assert second_person["identity_id"] == identity_id
    assert second_person["id"] != first_person["id"]

    first_membership = client.get(f"/api/cases/{first_case}/people").json()[0]
    second_membership = client.get(f"/api/cases/{second_case}/people").json()[0]
    assert first_membership["notes"] == "Notes for first case only"
    assert second_membership["notes"] == "Notes for second case only"
    assert first_membership["aliases"] == ["A. Example"]
    assert second_membership["aliases"] == ["Alex E."]

    duplicate_link = client.post(
        f"/api/cases/{second_case}/people",
        json={"name": "Alex Example", "identity_id": identity_id},
    )
    assert duplicate_link.status_code == 409


def test_add_person_can_create_sourced_relationship_in_same_transaction(client):
    case_id = create_case(client, "Relationship workspace")
    existing_person = client.post(
        f"/api/cases/{case_id}/people", json={"name": "Jordan Sample"}
    ).json()
    source = client.post(
        f"/api/cases/{case_id}/sources",
        json={"url": "https://example.org/public-filing", "title": "Public filing"},
    ).json()

    created = client.post(
        f"/api/cases/{case_id}/people",
        json={
            "name": "Morgan Example",
            "initial_relationship": {
                "other_person_id": existing_person["id"],
                "source_id": source["id"],
                "label": "Listed together in filing",
                "details": "The public filing names both people.",
                "confidence": 0.7,
                "status": "unreviewed",
            },
        },
    )
    assert created.status_code == 201, created.text
    new_person = created.json()
    relationships = client.get(f"/api/cases/{case_id}/relationships").json()
    assert len(relationships) == 1
    assert relationships[0]["source_person_id"] == new_person["id"]
    assert relationships[0]["target_person_id"] == existing_person["id"]
    assert relationships[0]["source"]["url"] == "https://example.org/public-filing"


def test_failed_initial_relationship_does_not_leave_a_person_or_identity(client):
    case_id = create_case(client, "Atomic create workspace")
    person_before = len(client.get(f"/api/cases/{case_id}/people").json())
    identities_before = len(client.get("/api/people").json())
    response = client.post(
        f"/api/cases/{case_id}/people",
        json={
            "name": "Should Roll Back",
            "initial_relationship": {
                "other_person_id": "missing-person",
                "source_id": "missing-source",
                "label": "Invalid connection",
            },
        },
    )
    assert response.status_code == 404
    assert len(client.get(f"/api/cases/{case_id}/people").json()) == person_before
    assert len(client.get("/api/people").json()) == identities_before
