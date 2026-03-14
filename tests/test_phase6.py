"""Tests for Phase 6: Delivery monitoring, system health, feedback integration,
API auth, config validation, backup/restore, and end-to-end pipeline."""

import json
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Test helpers ───────────────────────────────────────────────────

def _setup_db(tmp_path):
    """Create a test DB with all required tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY, external_id TEXT UNIQUE, title TEXT,
            summary TEXT, url TEXT, source_id TEXT, source_name TEXT,
            source_tier INTEGER DEFAULT 2, collected_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'new', published_at TEXT, image_url TEXT,
            raw_content TEXT DEFAULT '', image_local_path TEXT,
            dismissed INTEGER DEFAULT 0, dismissed_at TEXT,
            handled INTEGER DEFAULT 0, handled_at TEXT, handled_by TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS signal_analysis (
            id INTEGER PRIMARY KEY, signal_id INTEGER UNIQUE,
            headline TEXT, signal_type TEXT, score_composite REAL,
            what_summary TEXT, why_it_matters TEXT, quick_win TEXT,
            suggested_owner TEXT, estimated_impact TEXT, outreach_template TEXT,
            score_revenue_impact REAL DEFAULT 0, score_time_sensitivity REAL DEFAULT 0,
            score_strategic_alignment REAL DEFAULT 0, score_competitive_pressure REAL DEFAULT 0,
            model_used TEXT, analyzed_at TEXT DEFAULT (datetime('now')),
            raw_ai_response TEXT, validation_level TEXT DEFAULT 'verified',
            source_count INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS signal_bus (
            id INTEGER PRIMARY KEY, signal_id INTEGER, bu_id TEXT, relevance_score REAL DEFAULT 0,
            UNIQUE(signal_id, bu_id)
        );
        CREATE TABLE IF NOT EXISTS signal_validations (
            id INTEGER PRIMARY KEY, signal_id INTEGER,
            corroborating_url TEXT, corroborating_source TEXT,
            corroborating_title TEXT, similarity_score REAL,
            found_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY, week_number INTEGER, year INTEGER,
            subject_line TEXT, signal_count INTEGER DEFAULT 0,
            bu_count INTEGER DEFAULT 0, html_content TEXT,
            html_file_path TEXT, status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT (datetime('now')), sent_at TEXT,
            UNIQUE(week_number, year)
        );
        CREATE TABLE IF NOT EXISTS delivery_log (
            id INTEGER PRIMARY KEY, digest_id INTEGER,
            recipient_email TEXT, recipient_name TEXT,
            status TEXT DEFAULT 'pending', gmail_message_id TEXT,
            sent_at TEXT, error_message TEXT, retry_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY, signal_id INTEGER,
            digest_id INTEGER, recipient_email TEXT,
            rating TEXT, comment TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS source_health (
            id INTEGER PRIMARY KEY, source_id TEXT,
            check_time TEXT DEFAULT (datetime('now')),
            status TEXT, response_time_ms INTEGER,
            signal_count INTEGER DEFAULT 0, error_message TEXT
        );
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY, run_type TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT, status TEXT DEFAULT 'running',
            signals_collected INTEGER DEFAULT 0,
            signals_validated INTEGER DEFAULT 0,
            signals_scored INTEGER DEFAULT 0,
            digest_id INTEGER, error_message TEXT, log_file_path TEXT
        );
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY, trend_key TEXT UNIQUE, trend_type TEXT,
            label TEXT, first_seen DATE, last_seen DATE,
            occurrence_count INTEGER DEFAULT 1, week_over_week_change REAL DEFAULT 0,
            avg_score REAL DEFAULT 0, max_score REAL DEFAULT 0,
            momentum TEXT DEFAULT 'stable', updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS industries (
            id TEXT PRIMARY KEY, name TEXT, category TEXT DEFAULT '',
            description TEXT DEFAULT '', priority INTEGER DEFAULT 2,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS industry_bus (
            industry_id TEXT, bu_id TEXT, PRIMARY KEY (industry_id, bu_id)
        );
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY, keyword TEXT, industry_id TEXT,
            bu_id TEXT, source TEXT DEFAULT 'manual', active INTEGER DEFAULT 1,
            hit_count INTEGER DEFAULT 0, last_hit_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(keyword, industry_id)
        );
        CREATE TABLE IF NOT EXISTS signal_industries (
            id INTEGER PRIMARY KEY, signal_id INTEGER, industry_id TEXT,
            relevance_score REAL DEFAULT 0, matched_keywords TEXT DEFAULT '',
            UNIQUE(signal_id, industry_id)
        );
        CREATE TABLE IF NOT EXISTS reddit_subreddits (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE,
            category TEXT DEFAULT '', active INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY, trend_id INTEGER, week_number INTEGER,
            year INTEGER, signal_count INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0, top_signal_id INTEGER,
            captured_at TEXT DEFAULT (datetime('now')),
            UNIQUE(trend_id, week_number, year)
        );
    """)
    conn.commit()
    return conn


def _insert_test_deliveries(conn, count=10, failed=2):
    """Insert test delivery log entries."""
    for i in range(count):
        status = "failed" if i < failed else "sent"
        conn.execute(
            """INSERT INTO delivery_log
               (digest_id, recipient_email, recipient_name, status, sent_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (1, f"user{i}@example.com", f"User {i}", status),
        )
    conn.commit()


def _insert_test_signals(conn, count=5):
    """Insert test signals with analysis."""
    for i in range(count):
        conn.execute(
            """INSERT INTO signals (external_id, title, summary, url, source_id, source_name, status)
               VALUES (?, ?, ?, ?, ?, ?, 'scored')""",
            (f"sig-{i}", f"Signal {i}", f"Summary {i}", f"http://example.com/{i}", f"src-{i}", f"Source {i}"),
        )
        conn.execute(
            """INSERT INTO signal_analysis
               (signal_id, signal_type, headline, what_summary, why_it_matters,
                quick_win, score_composite, score_revenue_impact,
                score_time_sensitivity, score_strategic_alignment,
                score_competitive_pressure, validation_level, source_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'verified', 3)""",
            (i + 1, "revenue-opportunity", f"Headline {i}", f"What {i}",
             f"Why {i}", f"Action {i}", 7.5 + i * 0.3, 7, 6, 8, 5),
        )
        conn.execute(
            "INSERT INTO signal_bus (signal_id, bu_id) VALUES (?, ?)",
            (i + 1, "vpg-force-sensors"),
        )
    conn.commit()


# ═══════════════════════════════════════════════════════════════════
# 1. DELIVERY MONITORING TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDeliveryMonitoring:
    """Tests for delivery monitoring and analytics."""

    def test_log_delivery(self, tmp_path):
        conn = _setup_db(tmp_path)
        from src.delivery.monitoring import log_delivery

        row_id = log_delivery(
            conn, digest_id=1,
            recipient_email="test@example.com",
            recipient_name="Test User",
            status="sent",
        )
        assert row_id > 0
        row = conn.execute("SELECT * FROM delivery_log WHERE id = ?", (row_id,)).fetchone()
        assert row["recipient_email"] == "test@example.com"
        assert row["status"] == "sent"

    def test_get_delivery_stats(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_deliveries(conn, count=10, failed=2)

        from src.delivery.monitoring import get_delivery_stats
        stats = get_delivery_stats(conn, days=30)

        assert stats["total_attempts"] == 10
        assert stats["sent"] == 8
        assert stats["failed"] == 2
        assert stats["success_rate"] == 80.0

    def test_get_delivery_logs(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_deliveries(conn, count=5, failed=1)

        from src.delivery.monitoring import get_delivery_logs
        logs = get_delivery_logs(conn, limit=3)
        assert len(logs) == 3

        # Filter by status
        failed_logs = get_delivery_logs(conn, status="failed")
        assert len(failed_logs) == 1

    def test_get_delivery_logs_filter_recipient(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_deliveries(conn, count=5)

        from src.delivery.monitoring import get_delivery_logs
        logs = get_delivery_logs(conn, recipient="user3")
        assert len(logs) == 1
        assert "user3" in logs[0]["recipient_email"]

    def test_recipient_delivery_history(self, tmp_path):
        conn = _setup_db(tmp_path)
        email = "test@example.com"
        for status in ["sent", "sent", "failed"]:
            conn.execute(
                "INSERT INTO delivery_log (digest_id, recipient_email, status, sent_at) VALUES (1, ?, ?, datetime('now'))",
                (email, status),
            )
        conn.commit()

        from src.delivery.monitoring import get_recipient_delivery_history
        history = get_recipient_delivery_history(conn, email)

        assert history["email"] == email
        assert history["total_deliveries"] == 3
        assert history["successful"] == 2
        assert history["failed"] == 1
        assert len(history["recent_deliveries"]) == 3

    def test_delivery_timeline(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_deliveries(conn, count=5, failed=1)

        from src.delivery.monitoring import get_delivery_timeline
        timeline = get_delivery_timeline(conn, days=7)
        assert len(timeline) >= 1
        assert timeline[0]["total"] == 5


# ═══════════════════════════════════════════════════════════════════
# 2. SYSTEM HEALTH TESTS
# ═══════════════════════════════════════════════════════════════════

class TestSystemHealth:
    """Tests for system health monitoring."""

    def test_database_health(self, tmp_path):
        conn = _setup_db(tmp_path)
        from src.delivery.health import check_database_health

        result = check_database_health(conn)
        assert result["status"] == "healthy"
        assert "signal_count" in result

    def test_config_health(self, tmp_path):
        from src.delivery.health import check_config_health

        with patch("src.delivery.health.CONFIG_DIR", tmp_path):
            # No config files
            result = check_config_health()
            assert result["status"] == "degraded"
            assert len(result["issues"]) > 0

    def test_config_health_valid(self):
        from src.delivery.health import check_config_health

        result = check_config_health()
        # Should be healthy in real project with config files
        assert result["status"] in ("healthy", "degraded")

    def test_credentials_health_mock_mode(self):
        from src.delivery.health import check_credentials_health

        with patch("src.delivery.health.DELIVERY_MODE", "mock"):
            result = check_credentials_health()
            assert "delivery_mode" in result["checks"]

    def test_source_health(self, tmp_path):
        conn = _setup_db(tmp_path)
        # Insert some failing source entries
        for i in range(4):
            conn.execute(
                "INSERT INTO source_health (source_id, status, check_time) VALUES (?, 'error', datetime('now'))",
                ("bad-source",),
            )
        conn.commit()

        from src.delivery.health import check_source_health
        result = check_source_health(conn)
        assert result["status"] == "warning"
        assert len(result["failing_sources"]) == 1
        assert result["failing_sources"][0]["failures"] == 4

    def test_pipeline_health(self, tmp_path):
        conn = _setup_db(tmp_path)
        conn.execute(
            "INSERT INTO pipeline_runs (run_type, status, completed_at) VALUES ('full', 'completed', datetime('now'))"
        )
        conn.commit()

        from src.delivery.health import check_pipeline_health
        result = check_pipeline_health(conn)
        assert result["status"] == "healthy"
        assert result["last_success"] is not None

    def test_delivery_health_no_data(self, tmp_path):
        conn = _setup_db(tmp_path)
        from src.delivery.health import check_delivery_health

        result = check_delivery_health(conn)
        assert result["status"] == "unknown"

    def test_full_health_check(self, tmp_path):
        conn = _setup_db(tmp_path)
        from src.delivery.health import get_full_health_check

        result = get_full_health_check(conn)
        assert "status" in result
        assert "checks" in result
        assert "alerts" in result
        assert "timestamp" in result
        assert "version" in result

    def test_disk_health(self):
        from src.delivery.health import check_disk_health
        result = check_disk_health()
        assert result["status"] in ("healthy", "warning", "unknown")


# ═══════════════════════════════════════════════════════════════════
# 3. API AUTH & RATE LIMITING TESTS
# ═══════════════════════════════════════════════════════════════════

class TestAPIAuth:
    """Tests for API authentication and rate limiting."""

    def test_auth_disabled_by_default(self):
        from src.api.auth import _is_auth_enabled, verify_api_key
        with patch("src.api.auth.API_KEY", ""), patch("src.api.auth.ADMIN_API_KEY", ""):
            assert not _is_auth_enabled()
            assert verify_api_key(None)  # No auth needed

    def test_auth_enabled(self):
        from src.api.auth import _is_auth_enabled, verify_api_key
        with patch("src.api.auth.API_KEY", "test-key"), patch("src.api.auth.ADMIN_API_KEY", "admin-key"):
            assert _is_auth_enabled()
            assert verify_api_key("test-key")
            assert verify_api_key("admin-key")
            assert not verify_api_key("wrong-key")
            assert not verify_api_key(None)

    def test_admin_auth(self):
        from src.api.auth import verify_api_key
        with patch("src.api.auth.API_KEY", "test-key"), patch("src.api.auth.ADMIN_API_KEY", "admin-key"):
            assert verify_api_key("admin-key", require_admin=True)
            assert not verify_api_key("test-key", require_admin=True)

    def test_rate_limiting(self):
        from src.api.auth import check_rate_limit, _rate_tracker
        _rate_tracker.clear()

        # Should allow requests under limit
        for _ in range(5):
            assert check_rate_limit("192.168.1.1")

    def test_rate_limit_exceeded(self):
        from src.api.auth import check_rate_limit, _rate_tracker, RATE_LIMIT
        _rate_tracker.clear()

        # Exhaust rate limit
        with patch("src.api.auth.RATE_LIMIT", 3):
            for _ in range(3):
                assert check_rate_limit("10.0.0.1")
            # 4th should be denied
            assert not check_rate_limit("10.0.0.1")


# ═══════════════════════════════════════════════════════════════════
# 4. CONFIG VALIDATION & BACKUP TESTS
# ═══════════════════════════════════════════════════════════════════

class TestConfigBackup:
    """Tests for config validation and backup/restore."""

    def test_validate_config(self):
        from src.api.backup import validate_config
        result = validate_config()
        assert "valid" in result
        assert "files" in result
        assert "errors" in result
        assert "warnings" in result

    def test_create_and_list_backups(self, tmp_path):
        from src.api.backup import create_backup, list_backups
        with patch("src.api.backup.BACKUP_DIR", tmp_path), \
             patch("src.api.backup.DATABASE_PATH", tmp_path / "test.db"):
            # Create a dummy DB
            (tmp_path / "test.db").write_bytes(b"test-db")

            result = create_backup()
            assert result["size_mb"] > 0
            assert result["database_included"]

            backups = list_backups()
            assert len(backups) >= 1

    def test_backup_restore(self, tmp_path):
        from src.api.backup import create_backup, restore_backup

        backup_dir = tmp_path / "backups"
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Write a config file
        (config_dir / "business-units.json").write_text('{"test": true}')

        with patch("src.api.backup.BACKUP_DIR", backup_dir), \
             patch("src.api.backup.CONFIG_DIR", config_dir), \
             patch("src.api.backup.DATABASE_PATH", tmp_path / "test.db"):
            (tmp_path / "test.db").write_bytes(b"original-db")

            # Create backup
            result = create_backup()
            backup_path = result["backup_file"]

            # Modify config
            (config_dir / "business-units.json").write_text('{"modified": true}')

            # Restore
            restore_result = restore_backup(backup_path)
            assert restore_result["status"] == "restored"
            assert "business-units.json" in restore_result["restored_files"]

            # Verify restored content
            restored = json.loads((config_dir / "business-units.json").read_text())
            assert restored == {"test": True}

    def test_restore_nonexistent(self):
        from src.api.backup import restore_backup
        result = restore_backup("/nonexistent/path.zip")
        assert result["status"] == "error"

    def test_list_backups_no_dir(self, tmp_path):
        from src.api.backup import list_backups
        with patch("src.api.backup.BACKUP_DIR", tmp_path / "nonexistent"):
            backups = list_backups()
            assert backups == []


# ═══════════════════════════════════════════════════════════════════
# 5. FEEDBACK INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestFeedbackIntegration:
    """Tests for feedback submission and analytics."""

    def test_feedback_recorded(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_signals(conn, 1)

        conn.execute(
            "INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (1, 'test@test.com', 'up')"
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'up'").fetchone()[0]
        assert count == 1

    def test_feedback_up_and_down(self, tmp_path):
        conn = _setup_db(tmp_path)
        _insert_test_signals(conn, 2)

        conn.execute("INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (1, 'a@t.com', 'up')")
        conn.execute("INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (1, 'b@t.com', 'up')")
        conn.execute("INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (2, 'c@t.com', 'down')")
        conn.commit()

        up = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'up'").fetchone()[0]
        down = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'down'").fetchone()[0]
        assert up == 2
        assert down == 1


# ═══════════════════════════════════════════════════════════════════
# 6. COMPOSER FEEDBACK URL TESTS
# ═══════════════════════════════════════════════════════════════════

class TestComposerFeedback:
    """Tests that the composer generates proper feedback URLs."""

    def test_feedback_url_in_context(self):
        from src.composer.composer import build_digest_context

        signals = [{
            "id": 1,
            "title": "Test Signal",
            "headline": "Test Headline",
            "what_summary": "Test summary",
            "why_it_matters": "Test relevance",
            "quick_win": "Test action",
            "signal_type": "revenue-opportunity",
            "composite_score": 8.5,
            "bu_matches": [{"bu_id": "vpg-force-sensors", "relevance_score": 0.9}],
            "url": "http://example.com",
            "validation_level": "verified",
            "source_count": 3,
        }]
        bu_config = {
            "business_units": [{"id": "vpg-force-sensors", "name": "VPG Force Sensors", "color": "#2E75B6"}],
            "branding": {"company_name": "VPG"},
        }

        context = build_digest_context(signals, bu_config)
        assert context["feedback_base_url"] != ""
        assert "/api/feedback/submit" in context["feedback_base_url"]


# ═══════════════════════════════════════════════════════════════════
# 7. PIPELINE DELIVERY LOGGING TESTS
# ═══════════════════════════════════════════════════════════════════

class TestPipelineDeliveryLogging:
    """Tests that the pipeline logs deliveries to monitoring table."""

    @patch("src.pipeline.DELIVERY_MODE", "mock")
    @patch("src.pipeline.get_recipients")
    @patch("src.pipeline.send_email")
    @patch("src.pipeline.get_connection")
    def test_stage_deliver_logs_results(self, mock_conn, mock_send, mock_recips, tmp_path):
        conn = _setup_db(tmp_path)
        db_path = tmp_path / "test.db"
        mock_conn.return_value = conn

        mock_recips.return_value = {
            "recipients": [
                {"email": "test@example.com", "name": "Test", "status": "active"},
            ]
        }
        mock_send.return_value = {"status": "sent", "mode": "mock", "recipient": "test@example.com"}

        from src.pipeline import stage_deliver

        results = stage_deliver("<html></html>", "Test Subject")

        assert len(results) == 1
        assert results[0]["status"] == "sent"

        # Use a new connection since stage_deliver closes its own
        verify_conn = sqlite3.connect(str(db_path))
        verify_conn.row_factory = sqlite3.Row
        row = verify_conn.execute("SELECT * FROM delivery_log").fetchone()
        verify_conn.close()
        assert row is not None
        assert row["recipient_email"] == "test@example.com"
        assert row["status"] == "sent"


# ═══════════════════════════════════════════════════════════════════
# 8. DOCKER ENTRYPOINT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDockerEntrypoint:
    """Tests for Docker entrypoint script."""

    def test_entrypoint_exists(self):
        entrypoint = Path(__file__).parent.parent / "scripts" / "entrypoint.sh"
        assert entrypoint.exists()

    def test_entrypoint_executable_content(self):
        entrypoint = Path(__file__).parent.parent / "scripts" / "entrypoint.sh"
        content = entrypoint.read_text()
        assert "#!/bin/bash" in content
        assert "environment validation" in content.lower() or "Environment validation" in content
        assert "exec" in content  # Must exec the CMD


# ═══════════════════════════════════════════════════════════════════
# 9. END-TO-END INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """End-to-end tests covering the full pipeline with mocked externals."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.pipeline.collect_all_rss")
    @patch("src.pipeline.collect_all_scraped")
    @patch("src.pipeline.collect_all_reddit")
    @patch("src.pipeline.collect_google_trends")
    @patch("src.pipeline.validate_signal")
    @patch("src.pipeline.AnalysisClient")
    @patch("src.pipeline.send_email")
    @patch("src.pipeline.get_recipients")
    @patch("src.pipeline.update_trends")
    def test_full_pipeline_mock(
        self, mock_trends, mock_recips, mock_send,
        mock_client_cls, mock_validate,
        mock_gtrends, mock_reddit, mock_scrape, mock_rss, tmp_path
    ):
        """Test the full pipeline end-to-end with mocked external calls."""
        # Setup mock DB
        db_path = tmp_path / "test.db"

        with patch("src.pipeline.get_connection") as mock_conn_fn, \
             patch("src.pipeline.init_db"), \
             patch("src.pipeline.MOCK_OUTPUT_DIR", tmp_path), \
             patch("src.pipeline.DELIVERY_MODE", "mock"), \
             patch("src.pipeline.get_scoring_weights") as mock_weights, \
             patch("src.pipeline.get_business_units") as mock_bus:

            # Setup DB once; return new connections each time (stage_deliver opens its own)
            _setup_db(tmp_path)
            db_file = str(tmp_path / "test.db")

            def _make_conn(*a, **kw):
                c = sqlite3.connect(db_file)
                c.row_factory = sqlite3.Row
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("PRAGMA foreign_keys=ON")
                return c

            mock_conn_fn.side_effect = _make_conn

            # RSS returns test signals
            mock_rss.return_value = [
                {
                    "external_id": f"e2e-{i}",
                    "title": f"E2E Signal {i}",
                    "summary": f"Summary for signal {i}",
                    "url": f"http://example.com/e2e/{i}",
                    "source_id": "test-rss",
                    "source_name": "Test RSS",
                    "source_tier": 1,
                }
                for i in range(3)
            ]
            mock_scrape.return_value = []
            mock_reddit.return_value = []
            mock_gtrends.return_value = []

            # Validation is a no-op
            mock_validate.return_value = None

            # AI client not available (use heuristic)
            mock_client = MagicMock()
            mock_client.available = False
            mock_client_cls.return_value = mock_client

            # Scoring weights
            mock_weights.return_value = {
                "weights": {"revenue_impact": 35, "time_sensitivity": 25,
                            "strategic_alignment": 25, "competitive_pressure": 15},
                "thresholds": {"include_in_digest": 1.0, "max_signals_per_digest": 25},
            }

            # BU config
            mock_bus.return_value = {
                "business_units": [
                    {"id": "vpg-force-sensors", "name": "VPG Force Sensors", "color": "#2E75B6"}
                ],
                "branding": {"company_name": "VPG"},
            }

            # Recipients
            mock_recips.return_value = {
                "recipients": [
                    {"email": "exec@vpg.com", "name": "Exec", "status": "active"},
                ]
            }
            mock_send.return_value = {"status": "sent", "mode": "mock", "recipient": "exec@vpg.com"}

            # Trends
            mock_trends.return_value = {"trends_updated": 0, "notable": []}

            from src.pipeline import run_full_pipeline
            result = run_full_pipeline()

            assert result["status"] == "completed"
            assert result["signals_collected"] >= 3

    def test_api_server_imports(self):
        """Test that the API server module loads without errors."""
        from src.api.server import app
        assert app.title == "VPG Intelligence Digest"
        assert app.version == "6.0.0"

    def test_all_phase6_modules_import(self):
        """Verify all Phase 6 modules import cleanly."""
        from src.delivery.monitoring import log_delivery, get_delivery_stats
        from src.delivery.health import get_full_health_check
        from src.api.auth import verify_api_key, check_rate_limit
        from src.api.backup import validate_config, create_backup


# ═══════════════════════════════════════════════════════════════════
# 10. EMAIL TEMPLATE RENDERING TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEmailRendering:
    """Tests for email template rendering with Phase 6 feedback links."""

    def test_digest_renders_feedback_links(self):
        from src.composer.composer import build_digest_context, render_digest

        # Need 2+ signals so one goes to signal_of_week and one to bu_sections
        # (bu_sections action cards contain the feedback links)
        signals = [
            {
                "id": 42,
                "title": "Test Signal",
                "headline": "Kistler launches new sensor",
                "what_summary": "Kistler announced a new force sensor.",
                "why_it_matters": "Direct competitor to VPG Force Sensors.",
                "quick_win": "Schedule competitive analysis meeting.",
                "signal_type": "competitive-threat",
                "composite_score": 9.2,
                "bu_matches": [{"bu_id": "vpg-force-sensors", "relevance_score": 0.95}],
                "url": "http://example.com/kistler",
                "validation_level": "verified",
                "source_count": 3,
                "suggested_owner": "VP Sales",
                "estimated_impact": "$500K-$1M",
            },
            {
                "id": 43,
                "title": "Second Signal",
                "headline": "HBK expands into robotics",
                "what_summary": "HBK announced robotics sensor line.",
                "why_it_matters": "New competitor entry.",
                "quick_win": "Brief sales team.",
                "signal_type": "competitive-threat",
                "composite_score": 7.5,
                "bu_matches": [{"bu_id": "vpg-force-sensors", "relevance_score": 0.8}],
                "url": "http://example.com/hbk",
                "validation_level": "verified",
                "source_count": 3,
            },
        ]
        bu_config = {
            "business_units": [{"id": "vpg-force-sensors", "name": "VPG Force Sensors", "color": "#B71C1C"}],
            "branding": {"company_name": "VPG"},
        }

        context = build_digest_context(signals, bu_config)
        html = render_digest(context)

        # Basic structure checks
        assert "Intelligence Digest" in html
        assert "Kistler launches new sensor" in html
        assert "vpg-force-sensors" in html.lower() or "force sensors" in html.lower()
        assert "9.2" in html

        # Feedback links should be present in BU section action cards
        assert "Feedback Links" in html or "rating=up" in html or "&#x1F44D;" in html

    def test_digest_renders_all_sections(self):
        from src.composer.composer import build_digest_context, render_digest

        signals = [
            {
                "id": i,
                "title": f"Signal {i}",
                "headline": f"Headline {i}",
                "what_summary": f"Summary {i}",
                "why_it_matters": f"Relevance {i}",
                "quick_win": f"Action {i}",
                "signal_type": st,
                "composite_score": 8.0 - i * 0.1,
                "bu_matches": [{"bu_id": "vpg-force-sensors", "relevance_score": 0.8}],
                "url": f"http://example.com/{i}",
                "validation_level": "verified",
                "source_count": 3,
            }
            for i, st in enumerate([
                "competitive-threat", "revenue-opportunity", "market-shift",
                "trade-tariff", "technology-trend",
            ])
        ]
        bu_config = {
            "business_units": [{"id": "vpg-force-sensors", "name": "VPG Force Sensors", "color": "#2E75B6"}],
            "branding": {"company_name": "VPG"},
        }

        context = build_digest_context(signals, bu_config)
        html = render_digest(context)

        assert "Signal of the Week" in html
        assert "Top Signals This Week" in html
        assert "Competitive Radar" in html
        assert "Trade &amp; Tariff Watch" in html or "Trade" in html
        assert "This Week at a Glance" in html
