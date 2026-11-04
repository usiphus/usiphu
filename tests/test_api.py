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
    assert coverage.json()["specialties"] == 27
    assert coverage.json()["topics"] == 174
    assert coverage.json()["course_outcomes_catalogued"] == 73
    assert coverage.json()["official_outcomes_linked_at_topic_level"] == 47
    topics = client.get("/curriculum/topics", params={"q":"urinary retention"})
    assert topics.status_code == 200
    assert any("retention" in row["topic"].lower() for row in topics.json())


def test_practice_banks_and_resources():
    questions = client.get("/practice/questions")
    cases = client.get("/practice/cases")
    assert questions.status_code == 200 and len(questions.json()) >= 3
    drafts = client.get("/practice/questions", params={"review_status": "draft"})
    assert len(drafts.json()) == 20
    filtered = client.get("/practice/questions", params={"specialty": "urology", "difficulty": "easy", "bank_id": "starter-medical-bank"})
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["question_type"] == "single_best_answer"
    assert filtered.json()[0]["bank_id"] == "starter-medical-bank"
    bank_filtered = client.get("/practice/questions", params={"bank_id": "starter-medical-bank"})
    assert len(bank_filtered.json()) == 3
    banks = client.get("/practice/question-banks")
    assert banks.status_code == 200
    bank_rows = {row["bank_id"]: row for row in banks.json()}
    assert set(bank_rows) == {
        "starter-medical-bank", "pilot-urology-2026", "pilot-general-surgery-2026"
    }
    assert bank_rows["starter-medical-bank"]["question_count"] == 3
    assert bank_rows["pilot-urology-2026"]["question_count"] == 9
    assert bank_rows["pilot-general-surgery-2026"]["question_count"] == 8
    assert cases.status_code == 200 and len(cases.json()) >= 2
    assert client.get("/resources", params={"topic":"x"}).status_code == 422
    assert client.get("/resources", params={"topic":"renal colic","specialty":"Urology"}).status_code == 200


def test_content_validation_endpoint():
    response = client.get("/content/validation")
    assert response.status_code == 200
    result = response.json()
    assert result["specialties"] == 27
    assert result["topics"] == 174
    assert result["course_outcomes_catalogued"] == 73
    assert result["topics_without_verified_outcome_mapping"] == 112
    assert result["draft_questions"] == 20
    assert result["draft_cases"] == 2
    assert result["target_syllabus"] is None

def test_question_bank_text_search():
    response = client.get(
        "/practice/questions",
        params={"q": "posterior urethral valves"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["uro-002"]
