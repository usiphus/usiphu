"""SQLite persistence for isolated learner flashcards, reviews, and topic mastery."""
import os
import sqlite3
from datetime import date
from pathlib import Path

from usiphu.models import ReviewState

DEFAULT_DB = Path(os.getenv("USIPHU_DB_PATH", "usiphu_data.sqlite3"))


def _scoped_card_id(card_id: str, learner_id: str) -> str:
    if learner_id == "local" or card_id.startswith(f"{learner_id}:"):
        return card_id
    return f"{learner_id}:{card_id}"


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize(path: Path = DEFAULT_DB) -> None:
    """Create the schema and migrate the original single-learner database safely."""
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS flashcards (
          id TEXT PRIMARY KEY, owner_id TEXT NOT NULL DEFAULT 'local',
          specialty_id TEXT NOT NULL, topic_id TEXT NOT NULL,
          prompt TEXT NOT NULL, answer TEXT NOT NULL, source_url TEXT
        );
        CREATE TABLE IF NOT EXISTS generated_drafts (
          id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
          specialty_id TEXT NOT NULL, topic_id TEXT NOT NULL,
          payload_json TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'draft'
            CHECK(review_status='draft'),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_generated_drafts_owner
          ON generated_drafts(owner_id, created_at);
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
        CREATE TABLE IF NOT EXISTS learner_topic_progress (
          owner_id TEXT NOT NULL, topic_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'not_started',
          confidence INTEGER NOT NULL DEFAULT 0 CHECK(confidence BETWEEN 0 AND 5),
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(owner_id, topic_id)
        );
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(flashcards)")}
        if "owner_id" not in columns:
            db.execute("ALTER TABLE flashcards ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'")
        db.execute("CREATE INDEX IF NOT EXISTS idx_flashcards_owner ON flashcards(owner_id)")
        db.execute("""
            INSERT OR IGNORE INTO learner_topic_progress
                (owner_id, topic_id, status, confidence, updated_at)
            SELECT 'local', topic_id, status, confidence, updated_at FROM topic_progress
        """)


def save_flashcard(card: dict, path: Path = DEFAULT_DB, learner_id: str = "local") -> None:
    initialize(path)
    stored_card = {**card, "id": _scoped_card_id(card["id"], learner_id)}
    with connect(path) as db:
        cursor = db.execute("""
            INSERT INTO flashcards
                (id, owner_id, specialty_id, topic_id, prompt, answer, source_url)
            VALUES (:id, :owner_id, :specialty_id, :topic_id, :prompt, :answer, :source_url)
            ON CONFLICT(id) DO UPDATE SET
                prompt=excluded.prompt, answer=excluded.answer, source_url=excluded.source_url
            WHERE flashcards.owner_id=excluded.owner_id
        """, {**stored_card, "owner_id": learner_id})
        if cursor.rowcount != 1:
            raise ValueError("This flashcard ID is already owned by another learner")
        db.execute(
            "INSERT OR IGNORE INTO review_states(card_id,due_date) VALUES(?,?)",
            (stored_card["id"], date.today().isoformat()),
        )



def save_generated_drafts(
    cards: list[dict], path: Path = DEFAULT_DB, learner_id: str = "local"
) -> int:
    """Persist accepted cards in an isolated draft-only table, never the review queue."""
    initialize(path)
    saved = 0
    with connect(path) as db:
        for card in cards:
            if card.get("review_status") != "draft":
                raise ValueError("Only draft cards may be stored in generated_drafts")
            draft_id = _scoped_card_id(card["id"], learner_id)
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO generated_drafts
                    (id, owner_id, specialty_id, topic_id, payload_json, review_status)
                VALUES (?, ?, ?, ?, ?, 'draft')
                """,
                (
                    draft_id,
                    learner_id,
                    card["specialty_id"],
                    card["topic_id"],
                    json.dumps(card, ensure_ascii=False),
                ),
            )
            saved += cursor.rowcount
    return saved


def generated_drafts(
    path: Path = DEFAULT_DB, learner_id: str = "local"
) -> list[dict]:
    """List a learner's generated drafts; no approval or flashcard promotion occurs."""
    initialize(path)
    with connect(path) as db:
        rows = db.execute(
            """
            SELECT payload_json, review_status, created_at
            FROM generated_drafts WHERE owner_id=? ORDER BY created_at DESC, id
            """,
            (learner_id,),
        ).fetchall()
    return [
        {**json.loads(row["payload_json"]),
         "review_status": row["review_status"], "created_at": row["created_at"]}
        for row in rows
    ]


def due_cards(
    path: Path = DEFAULT_DB, on_date: date | None = None, learner_id: str = "local"
) -> list[dict]:
    initialize(path)
    with connect(path) as db:
        rows = db.execute("""
            SELECT f.*,r.repetitions,r.interval_days,r.ease_factor,r.due_date
            FROM flashcards f JOIN review_states r ON r.card_id=f.id
            WHERE f.owner_id=? AND r.due_date<=?
            ORDER BY r.due_date,f.id
        """, (learner_id, (on_date or date.today()).isoformat())).fetchall()
        return [dict(row) for row in rows]


def record_review(
    card_id: str, grade: int, state: ReviewState,
    path: Path = DEFAULT_DB, learner_id: str = "local",
) -> None:
    if not 0 <= grade <= 5:
        raise ValueError("grade must be between 0 and 5")
    initialize(path)
    card_id = _scoped_card_id(card_id, learner_id)
    with connect(path) as db:
        changed = db.execute("""
            UPDATE review_states SET repetitions=?,interval_days=?,ease_factor=?,due_date=?
            WHERE card_id=? AND EXISTS (
                SELECT 1 FROM flashcards WHERE flashcards.id=review_states.card_id
                AND flashcards.owner_id=?
            )
        """, (state.repetitions, state.interval_days, state.ease_factor,
              state.due_date, card_id, learner_id)).rowcount
        if changed != 1:
            raise KeyError(f"Unknown flashcard for learner: {card_id}")
        db.execute(
            "INSERT INTO review_events(card_id,grade,next_due) VALUES(?,?,?)",
            (card_id, grade, state.due_date),
        )


def set_topic_progress(
    topic_id: str, status: str, confidence: int,
    path: Path = DEFAULT_DB, learner_id: str = "local",
) -> None:
    if status not in {"not_started", "learning", "reviewing", "mastered"}:
        raise ValueError("Invalid topic status")
    if not 0 <= confidence <= 5:
        raise ValueError("confidence must be between 0 and 5")
    initialize(path)
    with connect(path) as db:
        db.execute("""
            INSERT INTO learner_topic_progress(owner_id,topic_id,status,confidence)
            VALUES(?,?,?,?)
            ON CONFLICT(owner_id,topic_id) DO UPDATE SET
                status=excluded.status, confidence=excluded.confidence,
                updated_at=CURRENT_TIMESTAMP
        """, (learner_id, topic_id, status, confidence))


def topic_progress(path: Path = DEFAULT_DB, learner_id: str = "local") -> list[dict]:
    initialize(path)
    with connect(path) as db:
        return [dict(row) for row in db.execute("""
            SELECT topic_id,status,confidence,updated_at
            FROM learner_topic_progress WHERE owner_id=? ORDER BY topic_id
        """, (learner_id,))]


def dashboard_stats(path: Path = DEFAULT_DB, learner_id: str = "local") -> dict[str, int]:
    initialize(path)
    with connect(path) as db:
        return {
            "flashcards": db.execute(
                "SELECT COUNT(*) FROM flashcards WHERE owner_id=?", (learner_id,)
            ).fetchone()[0],
            "due_cards": db.execute("""
                SELECT COUNT(*) FROM review_states r
                JOIN flashcards f ON f.id=r.card_id
                WHERE f.owner_id=? AND r.due_date<=?
            """, (learner_id, date.today().isoformat())).fetchone()[0],
            "reviews_completed": db.execute("""
                SELECT COUNT(*) FROM review_events e
                JOIN flashcards f ON f.id=e.card_id WHERE f.owner_id=?
            """, (learner_id,)).fetchone()[0],
            "topics_tracked": db.execute(
                "SELECT COUNT(*) FROM learner_topic_progress WHERE owner_id=?", (learner_id,)
            ).fetchone()[0],
            "topics_mastered": db.execute("""
                SELECT COUNT(*) FROM learner_topic_progress
                WHERE owner_id=? AND status='mastered'
            """, (learner_id,)).fetchone()[0],
        }
