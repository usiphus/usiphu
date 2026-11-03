"""FastAPI endpoints for curriculum, practice banks, and resource discovery."""
from fastapi import FastAPI, HTTPException, Query

from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.generator import build_generation_briefs, validate_generation_batch
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
def generator_briefs(specialty: str | None = None, topic: str | None = None) -> dict:
    """Return deterministic, source-linked generation jobs; no AI provider is implied."""
    try:
        briefs = build_generation_briefs(specialty_id=specialty, topic_id=topic)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "provider_configured": False,
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
