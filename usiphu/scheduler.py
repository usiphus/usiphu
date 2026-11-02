"""SM-2-inspired review scheduling (grades 0-5)."""
from datetime import date, timedelta
from usiphu.models import ReviewState


def schedule_review(state: ReviewState, grade: int, today: date | None = None) -> ReviewState:
    if not 0 <= grade <= 5:
        raise ValueError("grade must be between 0 and 5")
    today = today or date.today()
    quality_penalty = 5 - grade
    ease = max(1.3, state.ease_factor + (0.1 - quality_penalty * (0.08 + quality_penalty * 0.02)))
    if grade < 3:
        repetitions, interval = 0, 1
    else:
        repetitions = state.repetitions + 1
        interval = 1 if repetitions == 1 else 6 if repetitions == 2 else max(1, round(state.interval_days * ease))
    return ReviewState(card_id=state.card_id, repetitions=repetitions,
                       interval_days=interval, ease_factor=round(ease, 3),
                       due_date=(today + timedelta(days=interval)).isoformat())
