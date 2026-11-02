"""FastAPI endpoints for curriculum, practice banks, and resource discovery."""
from fastapi import FastAPI, HTTPException, Query

from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources

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
