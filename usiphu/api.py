"""FastAPI endpoints for curriculum, practice banks, and resource discovery."""
from fastapi import FastAPI, HTTPException, Query

from usiphu.ai_provider import (
    GenerationNotConfigured,
    generate_topic_cards,
    provider_status,
)
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.evidence import EvidenceRetrievalError
from usiphu.generator import EXAM_FORMATS, build_generation_briefs, validate_generation_batch
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources
from usiphu.validation import validate_content

app = FastAPI(title="Usiphu 2.0 API", version="2.0.0",
              description="Medical learning curriculum, practice, and resource discovery API.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/curriculum")
def curriculum() -> dict:
    return load_curriculum().model_dump()


@app.get("/curriculum/coverage")
def curriculum_coverage() -> dict:
    return coverage_summary(load_curriculum())


@app.get("/curriculum/topics")
def curriculum_topics(q: str | None = Query(default=None, min_length=1)) -> list[dict[str, str]]:
    rows = flatten_topics(load_curriculum())
    return [row for row in rows if not q or q.casefold() in
            (row["specialty"] + " " + row["domain"] + " " + row["topic"]).casefold()]


@app.get("/practice/questions")
def questions(specialty: str | None = None, topic: str | None = None) -> list[dict]:
    rows = [item.model_dump() for item in load_questions()]
    return [row for row in rows if (not specialty or row["specialty_id"] == specialty)
            and (not topic or row["topic_id"] == topic)]


@app.get("/practice/cases")
def cases(specialty: str | None = None) -> list[dict]:
    rows = [item.model_dump() for item in load_cases()]
    return [row for row in rows if not specialty or row["specialty_id"] == specialty]


@app.get("/resources")
def resources(topic: str = Query(min_length=2), specialty: str | None = None) -> list[dict[str, str]]:
    if len(topic) > 160 or (specialty and len(specialty) > 100):
        raise HTTPException(status_code=422, detail="Search terms are too long")
    return discover_resources(topic, specialty)


@app.get("/content/validation")
def content_validation() -> dict:
    """Return editorial coverage counts and fail fast on broken content references."""
    return validate_content()



@app.get("/generator/briefs")
def generator_briefs(
    specialty: str | None = None, topic: str | None = None,
    exam_format: str = "mixed",
) -> dict:
    """Return deterministic, source-linked generation jobs; no AI provider is implied."""
    try:
        briefs = build_generation_briefs(
            specialty_id=specialty, topic_id=topic, exam_format=exam_format
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    status = provider_status()
    return {
        "provider_configured": status["configured"],
        "provider": status,
        "generation_mode": "source_grounded_brief_only",
        "count": len(briefs),
        "briefs": briefs,
    }


@app.post("/generator/validate")
def generator_validate(payload: dict) -> dict:
    """Validate proposed generated cards before they enter editorial draft review."""
    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise HTTPException(status_code=422, detail="cards must be a list")
    try:
        briefs = build_generation_briefs()
        return validate_generation_batch(cards, briefs, payload.get("existing_cards", []))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@app.get("/generator/status")
def generator_status() -> dict:
    """Expose provider readiness without exposing secrets or making provider calls."""
    return provider_status()


@app.post("/generator/generate")
def generator_generate(payload: dict) -> dict:
    """Retrieve PubMed evidence and author review-required card drafts."""
    specialty = payload.get("specialty_id")
    topic = payload.get("topic_id")
    if not isinstance(specialty, str) or not specialty.strip() or len(specialty) > 100:
        raise HTTPException(status_code=422, detail="specialty_id is required")
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 160:
        raise HTTPException(status_code=422, detail="topic_id is required")
    exam_format = payload.get("exam_format", "mixed")
    if not isinstance(exam_format, str) or exam_format not in EXAM_FORMATS:
        raise HTTPException(status_code=422, detail="exam_format must be one of the supported formats")
    evidence_limit = payload.get("evidence_limit", 5)
    if not isinstance(evidence_limit, int) or not 1 <= evidence_limit <= 10:
        raise HTTPException(status_code=422, detail="evidence_limit must be between 1 and 10")
    try:
        return generate_topic_cards(
            specialty.strip(), topic.strip(), evidence_limit=evidence_limit,
            exam_format=exam_format,
        )
    except GenerationNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvidenceRetrievalError as exc:
        raise HTTPException(status_code=502, detail="PubMed evidence retrieval failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail="AI generation failed; no card was approved or saved") from exc
