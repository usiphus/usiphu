"""HTTP contract tests for the generator integration."""
from fastapi.testclient import TestClient

from usiphu.api import app

client = TestClient(app)


def test_generator_briefs_endpoint_returns_provider_boundary_and_objectives():
    response = client.get("/generator/briefs", params={"specialty": "urology", "topic": "pujo"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["provider_configured"], bool)
    assert payload["generation_mode"] == "source_grounded_brief_only"
    assert payload["count"] == 2
    assert payload["briefs"][0]["official_suez_outcomes"][0]["id"] == "SI-URO-01"


def test_generator_briefs_endpoint_rejects_unknown_topic():
    response = client.get("/generator/briefs", params={"topic": "missing-topic"})
    assert response.status_code == 404


def test_generator_validate_endpoint_rejects_non_list_payload():
    response = client.post("/generator/validate", json={"cards": "not-a-list"})
    assert response.status_code == 422


def test_generator_briefs_support_specialty_specific_osce_format():
    response = client.get(
        "/generator/briefs",
        params={"specialty": "urology", "topic": "pujo", "exam_format": "osce"},
    )
    assert response.status_code == 200
    brief = response.json()["briefs"][0]
    assert brief["output_contract"]["allowed_card_types"] == ["osce_station"]
    assert brief["specialty_exam_blueprint"]["title"] == "Urology"


def test_generator_briefs_reject_unsupported_exam_format():
    response = client.get(
        "/generator/briefs",
        params={"specialty": "urology", "topic": "pujo", "exam_format": "image_based"},
    )
    assert response.status_code == 422
