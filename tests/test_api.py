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


def test_practice_banks_and_resources():
    questions = client.get("/practice/questions")
    cases = client.get("/practice/cases")
    assert questions.status_code == 200 and len(questions.json()) >= 3
    assert cases.status_code == 200 and len(cases.json()) >= 2
    assert client.get("/resources", params={"topic":"x"}).status_code == 422
    assert client.get("/resources", params={"topic":"renal colic","specialty":"Urology"}).status_code == 200


def test_content_validation_endpoint():
    response = client.get("/content/validation")
    assert response.status_code == 200
    result = response.json()
    assert result["specialties"] == 13
    assert result["topics"] == 62
    assert result["draft_questions"] == 3
    assert result["draft_cases"] == 2
    assert result["target_syllabus"] is None

def test_question_bank_search_and_filters():
    filtered = client.get(
        "/practice/questions",
        params={"specialty": "urology", "difficulty": "easy", "review_status": "draft"},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == ["uro-001"]
    searched = client.get("/practice/questions", params={"q": "posterior urethral valves"})
    assert searched.status_code == 200
    assert [item["id"] for item in searched.json()] == ["uro-002"]
