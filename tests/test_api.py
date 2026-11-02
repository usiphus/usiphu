from fastapi.testclient import TestClient
from usiphu.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_curriculum_coverage_and_search():
    coverage = client.get("/curriculum/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["specialties"] >= 10
    topics = client.get("/curriculum/topics", params={"q":"urinary retention"})
    assert topics.status_code == 200
    assert any("retention" in row["topic"].lower() for row in topics.json())


def test_resources_reject_short_query():
    assert client.get("/resources", params={"topic":"x"}).status_code == 422
    assert client.get("/resources", params={"topic":"renal colic","specialty":"Urology"}).status_code == 200
