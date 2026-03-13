"""Tests for Phase 3 modules: feedback, events, outreach, India monitor, reports."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.db import init_db, get_connection


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with sample data."""
    db_path = tmp_path / "test.db"
    with patch("src.config.DATABASE_PATH", db_path), \
         patch("src.config.DATA_DIR", Path(__file__).parent.parent / "data"):
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        # Insert sample signals
        for i in range(5):
            conn.execute(
                "INSERT INTO signals (external_id, title, summary, url, source_id, source_name, source_tier, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'scored')",
                (f"sig-{i}", f"Test Signal {i}", f"Summary about robotics and automation {i}",
                 f"https://example.com/{i}", f"src-{i}", f"Source {i}", 1),
            )

        # Insert sample analyses
        signal_types = ["revenue-opportunity", "competitive-threat", "market-shift",
                        "trade-tariff", "technology-trend"]
        for i in range(5):
            conn.execute(
                "INSERT INTO signal_analysis (signal_id, signal_type, headline, what_summary, "
                "why_it_matters, quick_win, suggested_owner, estimated_impact, "
                "score_revenue_impact, score_time_sensitivity, score_strategic_alignment, "
                "score_competitive_pressure, score_composite) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (i + 1, signal_types[i], f"Headline {i}", f"What summary {i}",
                 f"Why it matters {i}", f"Quick win {i}", "BU Manager",
                 "$500K-$1M", 7, 6, 7, 5, 6.5 + i * 0.5),
            )

        # Insert BU associations
        bus = ["vpg-force-sensors", "vpg-foil-resistors", "micro-measurements",
               "vpg-onboard-weighing", "kelk"]
        for i in range(5):
            conn.execute(
                "INSERT INTO signal_bus (signal_id, bu_id, relevance_score) VALUES (?, ?, ?)",
                (i + 1, bus[i], 0.8),
            )

        # Insert some feedback
        conn.execute(
            "INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (1, 'test@test.com', 'up')"
        )
        conn.execute(
            "INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (2, 'test@test.com', 'down')"
        )
        conn.execute(
            "INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (3, 'test@test.com', 'up')"
        )

        conn.commit()
        yield conn
        conn.close()


@pytest.fixture
def events_file(tmp_path):
    """Create a temporary events config file."""
    events_path = tmp_path / "events.json"
    events_data = {
        "events": [
            {
                "id": "test-event",
                "name": "Test Event 2026",
                "description": "A test event",
                "start_date": "2026-06-01",
                "end_date": "2026-06-03",
                "location": "Test City",
                "relevant_bus": ["vpg-force-sensors"],
                "key_topics": ["robotics", "automation"],
                "competitors_attending": ["HBK"],
                "vpg_presence": "Exhibitor",
                "prep_weeks_before": 4,
            }
        ]
    }
    with open(events_path, "w") as f:
        json.dump(events_data, f)
    return events_path


# ── Feedback & Scoring Refinement Tests ───────────────────────────

class TestFeedbackRefinement:
    def test_feedback_summary_no_data(self, test_db):
        """Test feedback summary with minimal data."""
        from src.feedback.scoring_refinement import get_feedback_summary
        result = get_feedback_summary(test_db)
        assert result["total_feedback"] == 3

    def test_feedback_summary_with_data(self, test_db):
        """Test feedback summary returns positive rate."""
        from src.feedback.scoring_refinement import get_feedback_summary
        result = get_feedback_summary(test_db)
        assert result["positive"] == 2
        assert result["negative"] == 1
        assert result["positive_rate"] > 60

    def test_compute_scoring_adjustments(self, test_db):
        """Test scoring adjustment computation."""
        from src.feedback.scoring_refinement import compute_scoring_adjustments
        result = compute_scoring_adjustments(test_db)
        assert "signal_type_adjustments" in result
        assert "source_adjustments" in result
        assert "bu_adjustments" in result
        assert "summary" in result

    def test_score_multiplier_insufficient_data(self, test_db):
        """With <5 feedback items, multiplier should be 1.0."""
        from src.feedback.scoring_refinement import get_score_multiplier
        mult = get_score_multiplier("revenue-opportunity", "Source 1", "vpg-force-sensors", test_db)
        assert mult == 1.0

    def test_score_multiplier_with_enough_data(self, test_db):
        """With 5+ feedback items, multiplier should be adjusted."""
        from src.feedback.scoring_refinement import get_score_multiplier
        # Add more feedback to reach threshold
        for i in range(3, 8):
            test_db.execute(
                "INSERT INTO feedback (signal_id, recipient_email, rating) VALUES (?, 'test@test.com', 'up')",
                (min(i, 5),),
            )
        test_db.commit()
        mult = get_score_multiplier("revenue-opportunity", "Source 0", "vpg-force-sensors", test_db)
        assert 0.7 <= mult <= 1.3


# ── Events & Intel Packs Tests ────────────────────────────────────

class TestEvents:
    def test_load_default_events(self, tmp_path):
        """Test that default events are created when file is missing."""
        with patch("src.events.intel_packs.EVENTS_FILE", tmp_path / "events.json"):
            from src.events.intel_packs import list_events
            events = list_events()
            assert len(events) >= 4
            assert any(e["id"] == "aistech-2026" for e in events)

    def test_get_upcoming_events(self, events_file):
        """Test upcoming events detection."""
        with patch("src.events.intel_packs.EVENTS_FILE", events_file):
            from src.events.intel_packs import get_upcoming_events
            upcoming = get_upcoming_events(days_ahead=365)
            assert len(upcoming) >= 1
            assert upcoming[0]["days_until"] >= 0

    def test_add_event(self, events_file):
        """Test adding a new event."""
        with patch("src.events.intel_packs.EVENTS_FILE", events_file):
            from src.events.intel_packs import add_event, list_events
            new_event = {
                "id": "new-event",
                "name": "New Event",
                "start_date": "2026-12-01",
            }
            add_event(new_event)
            events = list_events()
            assert any(e["id"] == "new-event" for e in events)

    def test_delete_event(self, events_file):
        """Test deleting an event."""
        with patch("src.events.intel_packs.EVENTS_FILE", events_file):
            from src.events.intel_packs import delete_event, list_events
            assert delete_event("test-event")
            events = list_events()
            assert not any(e["id"] == "test-event" for e in events)

    def test_generate_intel_pack(self, events_file, test_db):
        """Test intel pack generation."""
        with patch("src.events.intel_packs.EVENTS_FILE", events_file):
            from src.events.intel_packs import generate_intel_pack
            pack = generate_intel_pack("test-event", test_db)
            assert "error" not in pack
            assert "event" in pack
            assert "talking_points" in pack
            assert "summary" in pack

    def test_generate_intel_pack_unknown_event(self, events_file, test_db):
        """Test intel pack for non-existent event."""
        with patch("src.events.intel_packs.EVENTS_FILE", events_file):
            from src.events.intel_packs import generate_intel_pack
            pack = generate_intel_pack("nonexistent", test_db)
            assert "error" in pack


# ── Outreach Templates Tests ──────────────────────────────────────

class TestOutreach:
    def test_generate_outreach(self, test_db):
        """Test outreach template generation for a signal."""
        from src.outreach.templates import generate_outreach
        result = generate_outreach(1, test_db)
        assert "error" not in result
        assert "templates" in result
        assert "email" in result["templates"]
        assert "linkedin" in result["templates"]
        assert "subject" in result["templates"]["email"]
        assert "body" in result["templates"]["email"]

    def test_generate_outreach_unknown_signal(self, test_db):
        """Test outreach for non-existent signal."""
        from src.outreach.templates import generate_outreach
        result = generate_outreach(999, test_db)
        assert "error" in result

    def test_batch_outreach(self, test_db):
        """Test batch outreach generation."""
        from src.outreach.templates import generate_batch_outreach
        results = generate_batch_outreach([1, 2, 3], test_db)
        assert len(results) == 3
        assert all("templates" in r or "error" in r for r in results)

    def test_outreach_template_variables(self, test_db):
        """Test that template variables are populated."""
        from src.outreach.templates import generate_outreach
        result = generate_outreach(1, test_db)
        body = result["templates"]["email"]["body"]
        assert "[Contact Name]" in body  # Placeholder for user to fill
        assert "VPG" in body or "Vishay" in body


# ── India Monitor Tests ───────────────────────────────────────────

class TestIndiaMonitor:
    def test_analyze_india_signals(self, test_db):
        """Test India signal analysis."""
        from src.india.monitor import analyze_india_signals
        result = analyze_india_signals(test_db)
        assert "summary" in result
        assert "talking_points" in result
        assert "competitor_vulnerabilities" in result
        assert len(result["talking_points"]) > 0

    def test_competitor_vulnerabilities(self, test_db):
        """Test competitor vulnerability assessment."""
        from src.india.monitor import analyze_india_signals
        result = analyze_india_signals(test_db)
        vulns = result["competitor_vulnerabilities"]
        assert len(vulns) > 0
        assert all("competitor" in v for v in vulns)
        assert all("vulnerability_level" in v for v in vulns)

    def test_talking_points_for_signal(self, test_db):
        """Test India talking points for a specific signal."""
        from src.india.monitor import get_india_talking_points_for_signal
        result = get_india_talking_points_for_signal(1, test_db)
        assert "talking_points" in result
        assert len(result["talking_points"]) > 0

    def test_talking_points_unknown_signal(self, test_db):
        """Test talking points for non-existent signal."""
        from src.india.monitor import get_india_talking_points_for_signal
        result = get_india_talking_points_for_signal(999, test_db)
        assert "error" in result


# ── Monthly Report Tests ──────────────────────────────────────────

class TestMonthlyReport:
    def test_generate_report(self, test_db):
        """Test monthly report generation."""
        from src.reports.monthly import generate_monthly_report
        now = datetime.now()
        result = generate_monthly_report(now.year, now.month, test_db)
        assert "period" in result
        assert "signal_stats" in result
        assert "feedback_stats" in result
        assert "bu_coverage" in result
        assert "source_rankings" in result

    def test_report_signal_stats(self, test_db):
        """Test signal statistics in monthly report."""
        from src.reports.monthly import generate_monthly_report
        now = datetime.now()
        result = generate_monthly_report(now.year, now.month, test_db)
        stats = result["signal_stats"]
        assert stats["total_collected"] >= 0
        assert "by_type" in stats

    def test_report_action_stats(self, test_db):
        """Test action statistics tracking."""
        from src.reports.monthly import generate_monthly_report
        now = datetime.now()
        result = generate_monthly_report(now.year, now.month, test_db)
        assert "action_stats" in result
        assert "handled" in result["action_stats"]
        assert "dismissed" in result["action_stats"]


# ── Meeting Prep Tests ────────────────────────────────────────────

class TestMeetingPrep:
    def test_list_target_accounts(self):
        """Test listing target accounts."""
        from src.reports.meeting_prep import list_target_accounts
        accounts = list_target_accounts()
        assert len(accounts) >= 5
        keys = [a["key"] for a in accounts]
        assert "caterpillar" in keys
        assert "humanetics" in keys

    def test_generate_meeting_brief(self, test_db):
        """Test meeting brief generation."""
        from src.reports.meeting_prep import generate_meeting_brief
        result = generate_meeting_brief("caterpillar", test_db)
        assert "error" not in result
        assert result["account"]["name"] == "Caterpillar Inc."
        assert "talking_points" in result
        assert "vpg_solutions" in result

    def test_meeting_brief_unknown_account(self, test_db):
        """Test meeting brief for non-existent account."""
        from src.reports.meeting_prep import generate_meeting_brief
        result = generate_meeting_brief("nonexistent", test_db)
        assert "error" in result

    def test_meeting_brief_has_india_point(self, test_db):
        """Test that meeting briefs include India advantage point."""
        from src.reports.meeting_prep import generate_meeting_brief
        result = generate_meeting_brief("caterpillar", test_db)
        india_points = [tp for tp in result["talking_points"]
                        if "india" in tp.get("category", "").lower() or
                        "india" in tp.get("point", "").lower()]
        assert len(india_points) > 0
