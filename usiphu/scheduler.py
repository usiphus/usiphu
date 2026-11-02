"""SM-2-inspired scheduling with bounded ease factor and explicit grades."""
from __future__ import annotations
from datetime import date, timedelta
from usiphu.models import ReviewState


def schedule_review(state: ReviewState, grade: int, today: date | None = None) -> ReviewState:
    """Return updated state. Grades follow Anki/SM-2 convention: 0-2 fail, 3-5 pass."""
    if not 0 <= grade <= 5:
        raise ValueError("grade must be between 0 and 5")
    today = today or date.today()
    ease = max(1.3, state.ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
    if grade < 3:
        repetitions = 0
        interval = 1
    else:
        repetitions = state.repetitions + 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = max(1, round(state.interval_days * ease))
    return ReviewState(card_id=state.card_id, repetitions=repetitions,
                       interval_days=interval, ease_factor=round(ease, 3),
                       due_date=today + timedelta(days=interval))
