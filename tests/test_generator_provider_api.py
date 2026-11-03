"""Tests for provider readiness and generation API safety boundaries."""
from fastapi.testclient import TestClient

from usiphu.api import app

client = TestClient(app)


def test_generator_status_never_exposes_secret(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-do-not-return")
    response = client.get("/generator/status")
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert "test-secret-do-not-return" not in response.text


def test_generate_endpoint_requires_server_side_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/generator/generate",
        json={"specialty_id": "urology", "topic_id": "pujo"},
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_generate_endpoint_validates_evidence_limit():
    response = client.post(
        "/generator/generate",
        json={"specialty_id": "urology", "topic_id": "pujo", "evidence_limit": 99},
    )
    assert response.status_code == 422
