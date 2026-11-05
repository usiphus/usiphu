"""Tests for SQL translation used by the hosted PostgreSQL compatibility layer."""
from usiphu.database import translate_sql


def test_qmark_parameters_translate_to_psycopg_placeholders():
    assert translate_sql("SELECT * FROM flashcards WHERE owner_id=? AND id=?") == (
        "SELECT * FROM flashcards WHERE owner_id=%s AND id=%s"
    )


def test_named_parameters_translate_to_psycopg_mapping_placeholders():
    assert translate_sql("INSERT INTO flashcards(id,prompt) VALUES(:id,:prompt)") == (
        "INSERT INTO flashcards(id,prompt) VALUES(%(id)s,%(prompt)s)"
    )


def test_insert_or_ignore_becomes_postgres_on_conflict():
    assert translate_sql(
        "INSERT OR IGNORE INTO review_states(card_id,due_date) VALUES(?,?)"
    ) == (
        "INSERT INTO review_states(card_id,due_date) VALUES(%s,%s) ON CONFLICT DO NOTHING"
    )


def test_existing_postgres_upsert_is_not_duplicated():
    statement = (
        "INSERT INTO faculty_reviewer_roles(reviewer_id,role) VALUES(?,?) "
        "ON CONFLICT(reviewer_id,role) DO NOTHING"
    )
    assert translate_sql(statement) == (
        "INSERT INTO faculty_reviewer_roles(reviewer_id,role) VALUES(%s,%s) "
        "ON CONFLICT(reviewer_id,role) DO NOTHING"
    )
