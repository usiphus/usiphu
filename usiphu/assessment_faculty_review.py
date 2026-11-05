"""Shared two-stage faculty review for generated and extracted assessment items.

Items remain drafts until independent clinical and examination approvals are recorded.
The service stores immutable content snapshots and enforces role and separation-of-duty
checks in the backend; the UI is not an authorization boundary.
"""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from usiphu.database import is_postgres
from usiphu.faculty_review import reviewer_roles
from usiphu.storage import DEFAULT_DB, connect, initialize

ReviewStage = Literal["clinical", "exam"]
ReviewDecision = Literal["approve", "request_changes", "reject"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_schema(path: Path = DEFAULT_DB) -> None:
    initialize(path)
    if is_postgres():
        return  # The hosted schema is installed through versioned Supabase migrations.
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS shared_assessment_reviews (
          item_id TEXT PRIMARY KEY,
          item_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          clinical_status TEXT NOT NULL DEFAULT 'pending',
          clinical_reviewer_id TEXT,
          clinical_reviewer_name TEXT,
          clinical_comment TEXT,
          exam_status TEXT NOT NULL DEFAULT 'pending',
          exam_reviewer_id TEXT,
          exam_reviewer_name TEXT,
          exam_comment TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shared_assessment_review_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_id TEXT NOT NULL,
          stage TEXT NOT NULL CHECK(stage IN ('clinical','exam')),
          decision TEXT NOT NULL CHECK(decision IN ('approve','request_changes','reject')),
          reviewer_id TEXT NOT NULL,
          reviewer_name TEXT NOT NULL,
          comment TEXT NOT NULL,
          content_snapshot_json TEXT NOT NULL,
          attestations_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_shared_assessment_events_item
          ON shared_assessment_review_events(item_id,id);
        """)


def _snapshot(payload: dict) -> tuple[str, str]:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def enqueue_assessment_for_review(
    item_id: str, item_type: str, payload: dict, path: Path = DEFAULT_DB
) -> None:
    """Add a generated/extracted item to the shared faculty queue as an editorial draft."""
    if not item_id.strip() or not item_type.strip() or not isinstance(payload, dict):
        raise ValueError("A stable item ID, item type and object payload are required.")
    encoded, digest = _snapshot(payload)
    _ensure_schema(path)
    now = _now()
    with connect(path) as db:
        existing = db.execute(
            "SELECT content_hash FROM shared_assessment_reviews WHERE item_id=?",
            (item_id,),
        ).fetchone()
        if existing and existing["content_hash"] == digest:
            return
        db.execute(
            """INSERT INTO shared_assessment_reviews
               (item_id,item_type,payload_json,content_hash,clinical_status,
                clinical_reviewer_id,clinical_reviewer_name,clinical_comment,
                exam_status,exam_reviewer_id,exam_reviewer_name,exam_comment,updated_at)
               VALUES(?,?,?,?, 'pending',NULL,NULL,NULL,'pending',NULL,NULL,NULL,?)
               ON CONFLICT(item_id) DO UPDATE SET
                 item_type=excluded.item_type,payload_json=excluded.payload_json,
                 content_hash=excluded.content_hash,clinical_status='pending',
                 clinical_reviewer_id=NULL,clinical_reviewer_name=NULL,
                 clinical_comment=NULL,exam_status='pending',
                 exam_reviewer_id=NULL,exam_reviewer_name=NULL,
                 exam_comment=NULL,updated_at=excluded.updated_at""",
            (item_id, item_type, encoded, digest, now),
        )


def list_assessment_review_queue(
    path: Path = DEFAULT_DB, include_released: bool = True
) -> list[dict]:
    _ensure_schema(path)
    query = "SELECT * FROM shared_assessment_reviews"
    if not include_released:
        query += " WHERE exam_status != 'approved'"
    query += " ORDER BY updated_at DESC,item_id"
    with connect(path) as db:
        rows = db.execute(query).fetchall()
    return [
        {**dict(row), "payload": json.loads(row["payload_json"]),
         "release_status": "exam_validated" if row["exam_status"] == "approved"
         else "clinically_reviewed" if row["clinical_status"] == "approved" else "draft"}
        for row in rows
    ]


def assessment_review_history(item_id: str, path: Path = DEFAULT_DB) -> list[dict]:
    _ensure_schema(path)
    with connect(path) as db:
        rows = db.execute(
            """SELECT stage,decision,reviewer_id,reviewer_name,comment,
                      content_snapshot_json,attestations_json,created_at
               FROM shared_assessment_review_events WHERE item_id=? ORDER BY id""",
            (item_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def record_assessment_review_decision(
    item_id: str, *, stage: ReviewStage, decision: ReviewDecision,
    reviewer_id: str, reviewer_name: str, comment: str,
    attestations: dict | None = None, path: Path = DEFAULT_DB,
) -> dict:
    if stage not in {"clinical", "exam"} or decision not in {"approve", "request_changes", "reject"}:
        raise ValueError("Invalid review stage or decision.")
    if not reviewer_id.strip() or not reviewer_name.strip() or not comment.strip():
        raise ValueError("Authenticated reviewer identity, reviewer name and comment are required.")
    role = "clinical_reviewer" if stage == "clinical" else "exam_reviewer"
    if role not in reviewer_roles(reviewer_id, path):
        raise PermissionError(f"This account is not assigned the {role} role.")
    _ensure_schema(path)
    now = _now()
    with connect(path) as db:
        row = db.execute(
            "SELECT * FROM shared_assessment_reviews WHERE item_id=?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown assessment review item: {item_id}")
        payload = json.loads(row["payload_json"])
        snapshot, digest = _snapshot(payload)
        if digest != row["content_hash"]:
            db.execute(
                """UPDATE shared_assessment_reviews SET content_hash=?,
                   clinical_status='pending',clinical_reviewer_id=NULL,
                   clinical_reviewer_name=NULL,clinical_comment=NULL,
                   exam_status='pending',exam_reviewer_id=NULL,
                   exam_reviewer_name=NULL,exam_comment=NULL,updated_at=?
                   WHERE item_id=?""", (digest, now, item_id)
            )
            row = db.execute(
                "SELECT * FROM shared_assessment_reviews WHERE item_id=?", (item_id,)
            ).fetchone()
        if stage == "exam" and row["clinical_status"] != "approved":
            raise ValueError("Examination validation is locked until clinical approval.")
        if stage == "exam" and row["clinical_reviewer_id"] == reviewer_id:
            raise ValueError("Clinical and examination approvals must be completed by different reviewers.")
        checks = attestations or {}
        if decision == "approve" and stage == "clinical":
            has_source = bool(payload.get("source_id") and payload.get("source_page"))
            has_evidence = bool(payload.get("evidence_sources") or payload.get("clinical_sources"))
            if not has_source and not has_evidence:
                raise ValueError("Clinical approval requires traceable source-paper provenance or clinical evidence.")
            prompt = payload.get("prompt") or payload.get("stem")
            has_mcq_key = (
                len(payload.get("options", [])) >= 2
                and bool(payload.get("correct_option_id"))
                and bool(payload.get("explanation"))
            )
            has_written_rubric = bool(payload.get("parts")) and all(
                part.get("prompt") and part.get("marking_points")
                for part in payload.get("parts", [])
            )
            has_structured_answer = bool(
                payload.get("answer") or payload.get("marking_criteria")
                or payload.get("station_tasks") and payload.get("marking_criteria")
                or payload.get("viva_questions") or payload.get("emq_items")
            )
            if not prompt or not (has_mcq_key or has_written_rubric or has_structured_answer):
                raise ValueError(
                    "Complete the edited prompt and a verified answer, marking rubric, "
                    "or format-specific assessment structure before clinical approval."
                )
            required = ("answer_verified", "rationale_verified", "evidence_checked", "safety_checked")
            if not all(checks.get(key) is True for key in required):
                raise ValueError("Complete all four clinical approval attestations.")
        if decision == "approve" and stage == "exam":
            required = ("single_best_answer", "stem_clear", "distractors_or_tasks_reviewed",
                        "curriculum_aligned", "level_appropriate")
            if not all(checks.get(key) is True for key in required):
                raise ValueError("Complete all five examination-validation attestations.")
        status = {"approve": "approved", "request_changes": "request_changes", "reject": "rejected"}[decision]
        if stage == "clinical":
            db.execute(
                """UPDATE shared_assessment_reviews SET clinical_status=?,
                   clinical_reviewer_id=?,clinical_reviewer_name=?,clinical_comment=?,
                   exam_status='pending',exam_reviewer_id=NULL,exam_reviewer_name=NULL,
                   exam_comment=NULL,updated_at=? WHERE item_id=?""",
                (status, reviewer_id, reviewer_name.strip(), comment.strip(), now, item_id),
            )
        else:
            db.execute(
                """UPDATE shared_assessment_reviews SET exam_status=?,
                   exam_reviewer_id=?,exam_reviewer_name=?,exam_comment=?,updated_at=?
                   WHERE item_id=?""",
                (status, reviewer_id, reviewer_name.strip(), comment.strip(), now, item_id),
            )
        db.execute(
            """INSERT INTO shared_assessment_review_events
               (item_id,stage,decision,reviewer_id,reviewer_name,comment,
                content_snapshot_json,attestations_json,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (item_id, stage, decision, reviewer_id, reviewer_name.strip(),
             comment.strip(), snapshot, json.dumps(checks, sort_keys=True), now),
        )
        updated = db.execute(
            "SELECT * FROM shared_assessment_reviews WHERE item_id=?", (item_id,)
        ).fetchone()
    return {**dict(updated), "payload": payload}
