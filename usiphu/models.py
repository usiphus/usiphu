"""Shared typed domain models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LearningObjective(BaseModel):
    id: str
    text: str
    level: Literal["know", "understand", "apply", "perform"] = "understand"


class Topic(BaseModel):
    id: str
    title: str
    objectives: list[LearningObjective] = Field(default_factory=list)
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


class Flashcard(BaseModel):
    id: str
    specialty_id: str
    topic_id: str
    prompt: str
    answer: str
    source_url: str | None = None


class ReviewGrade(BaseModel):
    grade: int = Field(ge=0, le=5)


class ReviewState(BaseModel):
    card_id: str
    repetitions: int = 0
    interval_days: int = 0
    ease_factor: float = 2.5
    due_date: date = Field(default_factory=date.today)


class MCQOption(BaseModel):
    id: str
    text: str


class MCQ(BaseModel):
    id: str
    specialty_id: str
    topic_id: str
    stem: str
    options: list[MCQOption]
    correct_option_id: str
    explanation: str
    source_url: str | None = None
    difficulty: Literal["easy", "moderate", "hard"] = "moderate"

    @field_validator("options")
    @classmethod
    def has_unique_option_ids(cls, options: list[MCQOption]) -> list[MCQOption]:
        ids = [option.id for option in options]
        if len(ids) != len(set(ids)):
            raise ValueError("MCQ option IDs must be unique")
        return options


class ClinicalCase(BaseModel):
    id: str
    specialty_id: str
    topic_id: str
    title: str
    scenario: str
    tasks: list[str]
    discussion_points: list[str] = Field(default_factory=list)
    source_url: str | None = None


class ReviewEvent(BaseModel):
    card_id: str
    grade: int
    reviewed_at: datetime
    next_due: date


class TopicProgress(BaseModel):
    topic_id: str
    status: Literal["not_started", "learning", "reviewing", "mastered"]
    confidence: int = Field(ge=0, le=5)
