"""Tests for local provider readiness and generation API safety boundaries."""
from fastapi.testclient import TestClient

from usiphu.api import app

client = TestClient(app)


def test_generator_status_never_exposes_secrets(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("USIPHU_OLLAMA_MODEL", "qwen2.5:7b")
    response = client.get("/generator/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["provider"] == "ollama"
    assert "api_key" not in response.text.lower()


def test_generate_endpoint_requires_configured_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    response = client.post(
        "/generator/generate",
        json={"specialty_id": "urology", "topic_id": "pujo"},
    )
    assert response.status_code == 503
    assert "OLLAMA_BASE_URL" in response.json()["detail"]


def test_generate_endpoint_validates_evidence_limit():
    response = client.post(
        "/generator/generate",
        json={"specialty_id": "urology", "topic_id": "pujo", "evidence_limit": 99},
    )
    assert response.status_code == 422
