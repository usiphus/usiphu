"""Two-stage, independent faculty sign-off for the USIPHU pilot MCQ banks.

The authored JSON banks remain immutable source material. Decisions and immutable
review snapshots live in SQLite; load_questions overlays the current release state.
"""
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from usiphu.curriculum import load_curriculum
from usiphu.storage import DEFAULT_DB, connect, initialize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PILOT_BANK_IDS = {"pilot-urology-2026", "pilot-general-surgery-2026"}
Decision = Literal["approve", "request_changes", "reject"]
Stage = Literal["clinical", "exam"]
ReviewerRole = Literal["clinical_reviewer", "exam_reviewer"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_schema(path: Path = DEFAULT_DB) -> None:
    initialize(path)
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS faculty_question_reviews (
          question_id TEXT PRIMARY KEY,
          clinical_status TEXT NOT NULL DEFAULT 'pending'
            CHECK(clinical_status IN ('pending','approved','request_changes','rejected')),
          clinical_reviewer_id TEXT,
          clinical_reviewer_name TEXT,
          clinical_comment TEXT,
          clinical_reviewed_at TEXT,
          exam_status TEXT NOT NULL DEFAULT 'pending'
            CHECK(exam_status IN ('pending','approved','request_changes','rejected')),
          exam_reviewer_id TEXT,
          exam_reviewer_name TEXT,
          exam_comment TEXT,
          exam_reviewed_at TEXT,
          content_snapshot_json TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS faculty_question_review_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          question_id TEXT NOT NULL,
          stage TEXT NOT NULL CHECK(stage IN ('clinical','exam')),
          decision TEXT NOT NULL CHECK(decision IN ('approve','request_changes','reject')),
          reviewer_id TEXT NOT NULL,
          reviewer_name TEXT NOT NULL,
          comment TEXT NOT NULL,
          content_snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_faculty_review_events_question
          ON faculty_question_review_events(question_id, id);
        CREATE TABLE IF NOT EXISTS faculty_reviewer_roles (
          reviewer_id TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('admin','clinical_reviewer','exam_reviewer')),
          granted_by TEXT NOT NULL,
          granted_at TEXT NOT NULL,
          PRIMARY KEY(reviewer_id, role)
        );
        CREATE TABLE IF NOT EXISTS faculty_role_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          reviewer_id TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('clinical_reviewer','exam_reviewer')),
          action TEXT NOT NULL CHECK(action IN ('grant','revoke')),
          actor_id TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_faculty_role_events_reviewer
          ON faculty_role_events(reviewer_id, id);
        """)



def _configured_subjects(variable: str) -> set[str]:
    return {
        value.strip()
        for value in os.getenv(variable, "").split(",")
        if value.strip()
    }


def _sync_bootstrap_roles(path: Path = DEFAULT_DB) -> None:
    """Apply environment-managed bootstrap roles without removing database grants."""
    _ensure_schema(path)
    configured = {
        "clinical_reviewer": _configured_subjects("USIPHU_CLINICAL_REVIEWER_SUBJECTS"),
        "exam_reviewer": _configured_subjects("USIPHU_EXAM_REVIEWER_SUBJECTS"),
    }
    now = _now()
    with connect(path) as db:
        for role, subjects in configured.items():
            for subject in subjects:
                db.execute(
                    """INSERT INTO faculty_reviewer_roles
                       (reviewer_id,role,granted_by,granted_at) VALUES(?,?,?,?)
                       ON CONFLICT(reviewer_id,role) DO NOTHING""",
                    (subject, role, "environment", now),
                )


def reviewer_roles(reviewer_id: str, path: Path = DEFAULT_DB) -> set[str]:
    """Return roles for an authenticated issuer-qualified subject identifier."""
    if not reviewer_id or not reviewer_id.strip():
        return set()
    _sync_bootstrap_roles(path)
    with connect(path) as db:
        rows = db.execute(
            "SELECT role FROM faculty_reviewer_roles WHERE reviewer_id=?",
            (reviewer_id.strip(),),
        ).fetchall()
    roles = {row["role"] for row in rows}
    if reviewer_id.strip() in _configured_subjects("USIPHU_ADMIN_SUBJECTS"):
        roles.add("admin")
    return roles


def list_reviewer_assignments(path: Path = DEFAULT_DB) -> list[dict]:
    """List configured faculty roles for the administrator workspace."""
    _sync_bootstrap_roles(path)
    with connect(path) as db:
        rows = db.execute(
            """SELECT reviewer_id,role,granted_by,granted_at
               FROM faculty_reviewer_roles ORDER BY reviewer_id,role"""
        ).fetchall()
    return [dict(row) for row in rows if row["role"] != "admin"]


def set_reviewer_role(
    actor_id: str,
    reviewer_id: str,
    role: ReviewerRole,
    *,
    enabled: bool,
    path: Path = DEFAULT_DB,
) -> None:
    """Grant/revoke clinical or exam reviewer access; only bootstrap admins may manage roles."""
    if role not in {"clinical_reviewer", "exam_reviewer"}:
        raise ValueError("Only clinical and examination reviewer roles can be managed here.")
    if not actor_id.strip() or not reviewer_id.strip():
        raise ValueError("Administrator and reviewer identities are required.")
    if actor_id.strip() == reviewer_id.strip():
        raise ValueError("Administrators cannot assign reviewer roles to themselves.")
    if "admin" not in reviewer_roles(actor_id, path):
        raise PermissionError("Only an administrator configured in USIPHU_ADMIN_SUBJECTS can manage reviewer roles.")
    configured_variable = (
        "USIPHU_CLINICAL_REVIEWER_SUBJECTS"
        if role == "clinical_reviewer" else "USIPHU_EXAM_REVIEWER_SUBJECTS"
    )
    if not enabled and reviewer_id.strip() in _configured_subjects(configured_variable):
        raise ValueError(
            f"This role is configured through {configured_variable}; remove the identity "
            "from that environment variable and restart USIPHU instead."
        )
    _ensure_schema(path)
    now = _now()
    action = "grant" if enabled else "revoke"
    with connect(path) as db:
        if enabled:
            db.execute(
                """INSERT INTO faculty_reviewer_roles
                   (reviewer_id,role,granted_by,granted_at) VALUES(?,?,?,?)
                   ON CONFLICT(reviewer_id,role) DO NOTHING""",
                (reviewer_id.strip(), role, actor_id.strip(), now),
            )
        else:
            db.execute(
                "DELETE FROM faculty_reviewer_roles WHERE reviewer_id=? AND role=?",
                (reviewer_id.strip(), role),
            )
        db.execute(
            """INSERT INTO faculty_role_events
               (reviewer_id,role,action,actor_id,created_at) VALUES(?,?,?,?,?)""",
            (reviewer_id.strip(), role, action, actor_id.strip(), now),
        )


def role_assignment_history(reviewer_id: str, path: Path = DEFAULT_DB) -> list[dict]:
    _ensure_schema(path)
    with connect(path) as db:
        rows = db.execute(
            """SELECT role,action,actor_id,created_at FROM faculty_role_events
               WHERE reviewer_id=? ORDER BY id""",
            (reviewer_id,),
        ).fetchall()
    return [dict(row) for row in rows]

def _pilot_questions(bank_dir: Path | None = None) -> list[dict]:
    directory = bank_dir or DATA_DIR / "question_banks"
    rows = []
    for path in sorted(directory.glob("pilot_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("bank_id") in PILOT_BANK_IDS:
            for question in payload.get("questions", []):
                rows.append({**question, "bank_id": payload["bank_id"], "bank_title": payload.get("title", "")})
    return rows


def list_pilot_questions(path: Path = DEFAULT_DB, bank_dir: Path | None = None) -> list[dict]:
    _ensure_schema(path)
    questions = _pilot_questions(bank_dir)
    with connect(path) as db:
        states = {
            row["question_id"]: dict(row)
            for row in db.execute("SELECT * FROM faculty_question_reviews")
        }
    for question in questions:
        state = states.get(question["id"], {})
        question["clinical_status"] = state.get("clinical_status", "pending")
        question["clinical_reviewer_name"] = state.get("clinical_reviewer_name")
        question["clinical_comment"] = state.get("clinical_comment")
        question["clinical_reviewed_at"] = state.get("clinical_reviewed_at")
        question["exam_status"] = state.get("exam_status", "pending")
        question["exam_reviewer_name"] = state.get("exam_reviewer_name")
        question["exam_comment"] = state.get("exam_comment")
        question["exam_reviewed_at"] = state.get("exam_reviewed_at")
        if state.get("content_snapshot_json"):
            saved_content = json.loads(state["content_snapshot_json"])
            for key in (
                "stem", "options", "correct_option_id", "explanation", "specialty_id",
                "topic_id", "difficulty", "source_id", "source_page", "source_page_end",
                "source_filename", "source_candidate_id", "transcription_status",
                "evidence_sources", "editorial_notes"
            ):
                if key in saved_content:
                    question[key] = saved_content[key]
        question["faculty_release_status"] = (
            "exam_validated" if question["exam_status"] == "approved"
            else "clinically_reviewed" if question["clinical_status"] == "approved"
            else "draft"
        )
    return questions


def review_history(question_id: str, path: Path = DEFAULT_DB) -> list[dict]:
    _ensure_schema(path)
    with connect(path) as db:
        return [dict(row) for row in db.execute(
            """SELECT stage,decision,reviewer_id,reviewer_name,comment,
                      content_snapshot_json,created_at
               FROM faculty_question_review_events
               WHERE question_id=? ORDER BY id""", (question_id,)
        )]


def record_faculty_decision(
    question_id: str,
    *,
    stage: Stage,
    decision: Decision,
    reviewer_id: str,
    reviewer_name: str,
    comment: str,
    content: dict | None = None,
    attestations: dict | None = None,
    path: Path = DEFAULT_DB,
    bank_dir: Path | None = None,
) -> dict:
    """Append a decision and update the two-stage state with separation of duties."""
    if stage not in {"clinical", "exam"} or decision not in {"approve", "request_changes", "reject"}:
        raise ValueError("Invalid review stage or decision.")
    if not reviewer_id.strip() or not reviewer_name.strip() or not comment.strip():
        raise ValueError("A stable reviewer identity, reviewer name and review comment are required.")
    required_role = "clinical_reviewer" if stage == "clinical" else "exam_reviewer"
    if required_role not in reviewer_roles(reviewer_id, path):
        raise PermissionError(f"This authenticated account is not assigned the {required_role} role.")

    questions = {item["id"]: item for item in list_pilot_questions(path, bank_dir)}
    if question_id not in questions:
        raise KeyError(f"Unknown pilot question: {question_id}")
    question = questions[question_id]
    updated = dict(question)
    if content:
        updated.update(content)
    if not updated.get("stem", "").strip() or not updated.get("explanation", "").strip():
        raise ValueError("Question stem and clinical rationale must be complete.")
    option_ids = [str(option.get("id")) for option in updated.get("options", [])]
    if len(option_ids) < 2 or len(option_ids) != len(set(option_ids)):
        raise ValueError("At least two uniquely identified answer options are required.")
    if updated.get("correct_option_id") not in option_ids:
        raise ValueError("The answer key must match one of the current options.")
    if updated.get("difficulty") not in {"easy", "moderate", "hard"}:
        raise ValueError("Difficulty must be easy, moderate or hard.")
    curriculum = load_curriculum()
    valid_topic_pairs = {
        (specialty.id, topic.id)
        for specialty in curriculum.specialties
        for domain in specialty.domains
        for topic in domain.topics
    }
    if (updated.get("specialty_id"), updated.get("topic_id")) not in valid_topic_pairs:
        raise ValueError("The question must map to an existing specialty and curriculum topic.")

    checks = attestations or {}
    if decision == "approve" and stage == "clinical":
        if updated.get("transcription_status") not in {"visually_verified", "corrected"}:
            raise ValueError("Clinical approval requires visually verified source transcription.")
        if not updated.get("source_id") or not updated.get("source_page"):
            raise ValueError("Clinical approval requires original paper and page provenance.")
        if not updated.get("evidence_sources"):
            raise ValueError("Clinical approval requires at least one traceable clinical evidence source.")
        required = ("answer_verified", "rationale_verified", "evidence_checked", "safety_checked")
        if not all(checks.get(key) is True for key in required):
            raise ValueError("Complete all four clinical approval attestations before approving.")

    if decision == "approve" and stage == "exam":
        required = ("single_best_answer", "stem_clear", "distractors_reviewed", "curriculum_aligned", "level_appropriate")
        if not all(checks.get(key) is True for key in required):
            raise ValueError("Complete all five examination-validation attestations before approving.")

    snapshot = {
        key: updated.get(key) for key in (
            "stem", "options", "correct_option_id", "explanation", "specialty_id",
            "topic_id", "difficulty", "source_id", "source_page", "source_page_end",
            "source_filename", "source_candidate_id", "transcription_status",
            "evidence_sources", "editorial_notes"
        )
    }
    content_snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    event_snapshot = {**snapshot, "review_attestations": checks}
    event_snapshot_json = json.dumps(event_snapshot, ensure_ascii=False, sort_keys=True)
    now = _now()
    _ensure_schema(path)
    with connect(path) as db:
        state = db.execute(
            "SELECT * FROM faculty_question_reviews WHERE question_id=?", (question_id,)
        ).fetchone()
        previous_snapshot = state["content_snapshot_json"] if state else None
        content_changed = previous_snapshot is not None and previous_snapshot != content_snapshot_json

        clinical_status = state["clinical_status"] if state else "pending"
        clinical_id = state["clinical_reviewer_id"] if state else None
        clinical_name = state["clinical_reviewer_name"] if state else None
        clinical_comment = state["clinical_comment"] if state else None
        clinical_at = state["clinical_reviewed_at"] if state else None
        exam_status = state["exam_status"] if state else "pending"
        exam_id = state["exam_reviewer_id"] if state else None
        exam_name = state["exam_reviewer_name"] if state else None
        exam_comment = state["exam_comment"] if state else None
        exam_at = state["exam_reviewed_at"] if state else None

        if content_changed:
            # Any content edit invalidates both approvals. The current clinical
            # reviewer may re-approve the edited version in this same transaction.
            clinical_status = "pending"
            clinical_id = clinical_name = clinical_comment = clinical_at = None
            exam_status = "pending"
            exam_id = exam_name = exam_comment = exam_at = None

        if stage == "exam" and clinical_status != "approved":
            raise ValueError("Examination validation is locked until clinical approval is complete.")
        if stage == "exam" and clinical_id == reviewer_id:
            raise ValueError("Clinical and examination approvals must be completed by different reviewers.")

        if stage == "clinical":
            clinical_status = {"approve": "approved", "request_changes": "request_changes", "reject": "rejected"}[decision]
            clinical_id, clinical_name, clinical_comment, clinical_at = reviewer_id, reviewer_name.strip(), comment.strip(), now
            exam_status = "pending"
            exam_id = exam_name = exam_comment = exam_at = None
        else:
            exam_status = {"approve": "approved", "request_changes": "request_changes", "reject": "rejected"}[decision]
            exam_id, exam_name, exam_comment, exam_at = reviewer_id, reviewer_name.strip(), comment.strip(), now

        db.execute(
            """INSERT INTO faculty_question_reviews
               (question_id,clinical_status,clinical_reviewer_id,clinical_reviewer_name,
                clinical_comment,clinical_reviewed_at,exam_status,exam_reviewer_id,
                exam_reviewer_name,exam_comment,exam_reviewed_at,content_snapshot_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(question_id) DO UPDATE SET
                clinical_status=excluded.clinical_status,
                clinical_reviewer_id=excluded.clinical_reviewer_id,
                clinical_reviewer_name=excluded.clinical_reviewer_name,
                clinical_comment=excluded.clinical_comment,
                clinical_reviewed_at=excluded.clinical_reviewed_at,
                exam_status=excluded.exam_status,
                exam_reviewer_id=excluded.exam_reviewer_id,
                exam_reviewer_name=excluded.exam_reviewer_name,
                exam_comment=excluded.exam_comment,
                exam_reviewed_at=excluded.exam_reviewed_at,
                content_snapshot_json=excluded.content_snapshot_json,
                updated_at=excluded.updated_at""",
            (question_id, clinical_status, clinical_id, clinical_name, clinical_comment,
             clinical_at, exam_status, exam_id, exam_name, exam_comment, exam_at,
             content_snapshot_json, now),
        )
        db.execute(
            """INSERT INTO faculty_question_review_events
               (question_id,stage,decision,reviewer_id,reviewer_name,comment,
                content_snapshot_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (question_id, stage, decision, reviewer_id, reviewer_name.strip(),
             comment.strip(), event_snapshot_json, now),
        )

    return {
        "question_id": question_id,
        "clinical_status": clinical_status,
        "exam_status": exam_status,
        "faculty_release_status": (
            "exam_validated" if exam_status == "approved"
            else "clinically_reviewed" if clinical_status == "approved"
            else "draft"
        ),
        "content_changed": content_changed,
    }


def faculty_release_statuses(path: Path = DEFAULT_DB) -> dict[str, dict]:
    """Return approved release states for overlaying onto the authored pilot banks."""
    _ensure_schema(path)
    with connect(path) as db:
        rows = db.execute("SELECT * FROM faculty_question_reviews").fetchall()
    release = {}
    for row in rows:
        state = {
            "review_status": (
                "exam_validated" if row["exam_status"] == "approved"
                else "clinically_reviewed" if row["clinical_status"] == "approved"
                else "draft"
            ),
            "human_signoff_status": (
                "rejected" if row["clinical_status"] == "rejected" or row["exam_status"] == "rejected"
                else "approved" if row["exam_status"] == "approved" else "pending"
            ),
            "clinical_reviewed_by": row["clinical_reviewer_name"],
            "clinical_reviewed_at": row["clinical_reviewed_at"],
            "exam_validated_by": row["exam_reviewer_name"],
            "exam_validated_at": row["exam_reviewed_at"],
            "reviewed_by": (
                f"Clinical: {row['clinical_reviewer_name']}; Examination: {row['exam_reviewer_name']}"
                if row["exam_status"] == "approved"
                else row["clinical_reviewer_name"]
            ),
            "reviewed_at": (
                row["exam_reviewed_at"] if row["exam_status"] == "approved"
                else row["clinical_reviewed_at"]
            ),
            "faculty_review_comments": [row["clinical_comment"], row["exam_comment"]],
        }
        # The learner-facing bank must use the exact version faculty approved,
        # not the earlier JSON transcription if a reviewer corrected the item.
        if row["content_snapshot_json"]:
            state.update(json.loads(row["content_snapshot_json"]))
        release[row["question_id"]] = state
    return release
