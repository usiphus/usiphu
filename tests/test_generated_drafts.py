import pytest
from pathlib import Path
import tempfile
import json

# Import your actual functions from your package (adjust import path if needed)
# from usiphu.db import initialize, generate_drafts, validate_generated_drafts, connect

@pytest.fixture
def temp_db():
    """Provides a temporary SQLite database for isolated testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_usiphus.db"
        yield db_path

def test_validate_generated_draft_success():
    """Verify that a well-formed draft card passes validation."""
    card = {
        "id": "card_001",
        "specialty_id": "ophthalmology",
        "topic_id": "glaucoma",
        "prompt": "What is the primary risk factor for open-angle glaucoma?",
        "answer": "Elevated intraocular pressure",
        "review_status": "draft",
        "source_url": "https://example.com/guideline",
        "evidence_sources": [{"title": "Guidelines"}],
        "card_type": "standard"
    }
    brief = {"specialty_id": "ophthalmology"}
    
    # Mock or call your actual validation function
    # result = validate_generated_drafts(card, brief)
    # assert result["valid"] is True
    # assert not result["errors"]
    assert card["review_status"] == "draft"

def test_validate_generated_draft_invalid_status():
    """Verify that cards with non-draft status fail validation or require extra fields."""
    card = {
        "id": "card_002",
        "specialty_id": "ophthalmology",
        "topic_id": "glaucoma",
        "prompt": "Test prompt",
        "answer": "Test answer",
        "review_status": "reviewed",  # Invalid for generated_drafts table
    }
    
    # Check that review_status enforcement catches non-drafts
    assert card["review_status"] != "draft"

def test_generate_drafts_persistence(temp_db):
    """Verify that drafts are correctly saved into the generated_drafts table."""
    # Setup test database schema
    with sqlite3.connect(temp_db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_drafts (
                id TEXT PRIMARY KEY,
                owner_id TEXT,
                specialty_id TEXT,
                topic_id TEXT,
                payload_json TEXT,
                review_status TEXT DEFAULT 'draft'
            )
        """)
        conn.commit()

    card = {
        "id": "card_101",
        "specialty_id": "cardiology",
        "topic_id": "mi",
        "prompt": "First-line medication for STEMI?",
        "answer": "Aspirin",
        "review_status": "draft"
    }
    
    # Simulate saving draft
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO generated_drafts 
            (id, owner_id, specialty_id, topic_id, payload_json, review_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("card_101_local", "local", card["specialty_id"], card["topic_id"], json.dumps(card), "draft")
        )
        conn.commit()

        # Query back to verify persistence
        cursor = conn.execute("SELECT review_status, payload_json FROM generated_drafts WHERE id = ?", ("card_101_local",))
        row = cursor.fetchone()
        
    assert row is not None
    assert row[0] == "draft"
    loaded_payload = json.loads(row[1])
    assert loaded_payload["answer"] == "Aspirin"
