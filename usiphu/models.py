"""Typed domain models."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
