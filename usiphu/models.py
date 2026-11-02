"""Typed domain models with explicit curriculum and clinical review states."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator
ReviewStatus = Literal["draft", "clinically_reviewed", "exam_validated", "retired"]
CoverageStatus = Literal["planned", "mapped", "sourced", "reviewed", "exam_validated"]


class Objective(BaseModel):
    id: str
    text: str
    level: Literal["know", "understand", "apply", "perform"] = "understand"


class Topic(BaseModel):
    id: str
    title: str
    objectives: list[Objective] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exam_weight: Literal["low", "medium", "high", "unknown"] = "unknown"
    coverage_status: CoverageStatus = "mapped"
    source_refs: list[str] = Field(default_factory=list)
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    syllabus_refs: list[str] = Field(default_factory=list)


class Domain(BaseModel):
    id: str
    title: str
    topics: list[Topic] = Field(default_factory=list)


class Specialty(BaseModel):
    id: str
    title: str
    domains: list[Domain] = Field(default_factory=list)


class Curriculum(BaseModel):
    version: str
    description: str
    target_syllabus: str | None = None
    jurisdiction: str | None = None
    syllabus_version: str | None = None
    specialties: list[Specialty]


class Option(BaseModel):
    id: str
    text: str


class MCQ(BaseModel):
    id: str
    specialty_id: str
    topic_id: str
    stem: str
    options: list[Option]
    correct_option_id: str
    explanation: str
    source_url: str | None = None
    source_title: str | None = None
    source_date: str | None = None
    jurisdiction: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_status: ReviewStatus = "draft"
    difficulty: Literal["easy", "moderate", "hard"] = "moderate"

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[Option]) -> list[Option]:
        ids = [option.id for option in value]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise ValueError("MCQ requires at least two options with unique IDs")
        return value


class ReviewState(BaseModel):
    card_id: str
    repetitions: int = 0
    interval_days: int = 0
    ease_factor: float = 2.5
    due_date: str


class ClinicalCase(BaseModel):
    id: str
    specialty_id: str
    topic_id: str
    title: str
    scenario: str
    tasks: list[str]
    discussion_points: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_title: str | None = None
    source_date: str | None = None
    jurisdiction: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_status: ReviewStatus = "draft"
