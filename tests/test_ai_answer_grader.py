"""Tests for rubric-constrained AI-assisted written-answer review."""
import json

import pytest

import usiphu.ai_answer_grader as grader
from usiphu.ai_provider import GenerationNotConfigured


@pytest.fixture
def assessment():
    return {
        "id": "meq-demo",
        "assessment_type": "meq",
        "prompt": "Describe the initial management.",
        "scenario": "A patient presents acutely.",
        "parts": [{
            "id": "part-1",
            "prompt": "Outline the first steps.",
            "marking_points": [
                {"point": "Assess ABC", "acceptable_terms": ["ABC"], "marks": 2},
                {"point": "Establish IV access", "acceptable_terms": ["IV access"], "marks": 1},
            ],
        }],
    }


def _response(marks=(2, 1), confidence="high"):
    return json.dumps({
        "parts": [{
            "part_id": "part-1",
            "points": [
                {"point_index": 1, "marks_awarded": marks[0], "reason": "Recognized the assessment.",
                 "evidence_from_answer": "airway, breathing, circulation", "uncertainty": "none"},
                {"point_index": 2, "marks_awarded": marks[1], "reason": "Recognized access.",
                 "evidence_from_answer": "insert IV access", "uncertainty": "none"},
            ],
            "confidence": confidence,
            "uncertainties": [],
        }]
    })


def test_ai_grader_returns_provisional_human_review_result(monkeypatch, assessment):
    monkeypatch.setattr(grader, "provider_status", lambda: {"configured": True, "model": "local-test"})
    monkeypatch.setattr(grader, "_ollama_chat", lambda prompt, model: _response())
    result = grader.grade_assessment_answers(
        assessment, {"part-1": "Assess airway, breathing and circulation; insert IV access."}
    )
    assert result["marks_awarded"] == 3
    assert result["marks_available"] == 3
    assert result["official_mark"] is False
    assert result["human_review_required"] is True
    assert result["parts"][0]["points"][0]["point"] == "Assess ABC"


def test_ai_grader_rejects_marks_above_rubric(monkeypatch, assessment):
    monkeypatch.setattr(grader, "provider_status", lambda: {"configured": True, "model": "local-test"})
    monkeypatch.setattr(grader, "_ollama_chat", lambda prompt, model: _response((3, 1)))
    with pytest.raises(grader.AnswerGradingError, match="outside the rubric limit"):
        grader.grade_assessment_answers(assessment, {"part-1": "Some answer"})


def test_ai_grader_rejects_unknown_or_missing_rubric_points(monkeypatch, assessment):
    monkeypatch.setattr(grader, "provider_status", lambda: {"configured": True, "model": "local-test"})
    broken = json.loads(_response())
    broken["parts"][0]["points"].pop()
    monkeypatch.setattr(grader, "_ollama_chat", lambda prompt, model: json.dumps(broken))
    with pytest.raises(grader.AnswerGradingError, match="every rubric point"):
        grader.grade_assessment_answers(assessment, {"part-1": "Some answer"})


def test_ai_grader_requires_nonempty_answer(assessment):
    with pytest.raises(grader.AnswerGradingError, match="Enter at least one answer"):
        grader.grade_assessment_answers(assessment, {"part-1": ""})


def test_ai_grader_requires_configured_local_provider(monkeypatch, assessment):
    monkeypatch.setattr(grader, "provider_status", lambda: {"configured": False, "model": "local-test"})
    with pytest.raises(GenerationNotConfigured):
        grader.grade_assessment_answers(assessment, {"part-1": "Answer"})
