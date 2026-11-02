"""SQLite persistence for learner flashcards and review activity."""
import os
import sqlite3
from datetime import date
from pathlib import Path
from usiphu.models import ReviewState

DEFAULT_DB = Path(os.getenv("USIPHU_DB_PATH", "usiphu_data.sqlite3"))


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize(path: Path = DEFAULT_DB) -> None:
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS flashcards (
          id TEXT PRIMARY KEY, specialty_id TEXT NOT NULL, topic_id TEXT NOT NULL,
          prompt TEXT NOT NULL, answer TEXT NOT NULL, source_url TEXT
        );
        CREATE TABLE IF NOT EXISTS review_states (
          card_id TEXT PRIMARY KEY REFERENCES flashcards(id) ON DELETE CASCADE,
          repetitions INTEGER NOT NULL DEFAULT 0, interval_days INTEGER NOT NULL DEFAULT 0,
          ease_factor REAL NOT NULL DEFAULT 2.5, due_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL,
          grade INTEGER NOT NULL CHECK(grade BETWEEN 0 AND 5),
          reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, next_due TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topic_progress (
          topic_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'not_started',
          confidence INTEGER NOT NULL DEFAULT 0 CHECK(confidence BETWEEN 0 AND 5),
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def save_flashcard(card: dict, path: Path = DEFAULT_DB) -> None:
    initialize(path)
    with connect(path) as db:
        db.execute("""INSERT INTO flashcards VALUES(:id,:specialty_id,:topic_id,:prompt,:answer,:source_url)
        ON CONFLICT(id) DO UPDATE SET prompt=excluded.prompt, answer=excluded.answer,
        source_url=excluded.source_url""", card)
        db.execute("INSERT OR IGNORE INTO review_states(card_id,due_date) VALUES(?,?)",
                   (card["id"], date.today().isoformat()))


def due_cards(path: Path = DEFAULT_DB, on_date: date | None = None) -> list[dict]:
    initialize(path)
    with connect(path) as db:
        rows = db.execute("""SELECT f.*,r.repetitions,r.interval_days,r.ease_factor,r.due_date
        FROM flashcards f JOIN review_states r ON r.card_id=f.id
        WHERE r.due_date<=? ORDER BY r.due_date,f.id""",
        ((on_date or date.today()).isoformat(),)).fetchall()
        return [dict(row) for row in rows]


def record_review(card_id: str, grade: int, state: ReviewState, path: Path = DEFAULT_DB) -> None:
    with connect(path) as db:
        changed = db.execute("""UPDATE review_states SET repetitions=?,interval_days=?,
        ease_factor=?,due_date=? WHERE card_id=?""",
        (state.repetitions, state.interval_days, state.ease_factor, state.due_date, card_id)).rowcount
        if changed != 1:
            raise KeyError(f"Unknown flashcard: {card_id}")
        db.execute("INSERT INTO review_events(card_id,grade,next_due) VALUES(?,?,?)",
                   (card_id, grade, state.due_date))


def dashboard_stats(path: Path = DEFAULT_DB) -> dict[str, int]:
    initialize(path)
    with connect(path) as db:
        return {"flashcards": db.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0],
                "due_cards": db.execute("SELECT COUNT(*) FROM review_states WHERE due_date<=?",
                                        (date.today().isoformat(),)).fetchone()[0],
                "reviews_completed": db.execute("SELECT COUNT(*) FROM review_events").fetchone()[0]}
