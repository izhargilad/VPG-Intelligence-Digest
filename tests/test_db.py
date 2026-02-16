"""Tests for the database module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.db import get_connection, init_db, insert_signal, get_signals_by_status, update_signal_status


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


class TestDatabase:
    def test_init_creates_tables(self, tmp_db):
        cursor = tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "signals" in tables
        assert "signal_validations" in tables
        assert "signal_analysis" in tables
        assert "digests" in tables
        assert "delivery_log" in tables
        assert "feedback" in tables

    def test_insert_signal(self, tmp_db):
        signal = {
            "external_id": "test-123",
            "title": "Test Signal",
            "summary": "A test signal",
            "url": "https://example.com/test",
            "source_id": "test-source",
            "source_name": "Test Source",
            "source_tier": 1,
            "published_at": "2026-02-16T00:00:00",
            "raw_content": None,
            "image_url": None,
        }
        row_id = insert_signal(tmp_db, signal)
        assert row_id > 0

    def test_duplicate_signal_ignored(self, tmp_db):
        signal = {
            "external_id": "dupe-123",
            "title": "Duplicate Signal",
            "summary": "This should be inserted once",
            "url": "https://example.com/dupe",
            "source_id": "test-source",
            "source_name": "Test Source",
            "source_tier": 1,
        }
        id1 = insert_signal(tmp_db, signal)
        id2 = insert_signal(tmp_db, signal)
        # Second insert should be ignored (INSERT OR IGNORE)
        cursor = tmp_db.execute("SELECT COUNT(*) FROM signals WHERE external_id = 'dupe-123'")
        assert cursor.fetchone()[0] == 1

    def test_get_signals_by_status(self, tmp_db):
        signal = {
            "external_id": "status-test",
            "title": "Status Test",
            "url": "https://example.com/status",
            "source_id": "src",
            "source_name": "Src",
            "source_tier": 2,
        }
        insert_signal(tmp_db, signal)
        new_signals = get_signals_by_status(tmp_db, "new")
        assert len(new_signals) >= 1

    def test_update_signal_status(self, tmp_db):
        signal = {
            "external_id": "update-test",
            "title": "Update Test",
            "url": "https://example.com/update",
            "source_id": "src",
            "source_name": "Src",
            "source_tier": 2,
        }
        insert_signal(tmp_db, signal)

        # Get the signal ID
        signals = get_signals_by_status(tmp_db, "new")
        signal_id = signals[0]["id"]

        update_signal_status(tmp_db, signal_id, "validated")
        validated = get_signals_by_status(tmp_db, "validated")
        assert any(s["id"] == signal_id for s in validated)
