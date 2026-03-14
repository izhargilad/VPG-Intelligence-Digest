"""Tests for Phase 5 features: Cross-BU matching, ROI links, source health,
quick stats, scheduler, Docker deployment, and test digest sending."""

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest


# ── Test helpers ───────────────────────────────────────────────────

def _setup_db(tmp_path):
    """Create a test DB with required tables and sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY, external_id TEXT UNIQUE, title TEXT,
        summary TEXT, url TEXT, source_name TEXT, source_type TEXT,
        source_tier INTEGER DEFAULT 2, collected_at TEXT, status TEXT DEFAULT 'new',
        published_at TEXT, image_url TEXT, raw_content TEXT DEFAULT '',
        dismissed INTEGER DEFAULT 0, handled INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_analysis (
        id INTEGER PRIMARY KEY, signal_id INTEGER,
        headline TEXT, signal_type TEXT, score_composite REAL,
        what_summary TEXT, why_it_matters TEXT, quick_win TEXT,
        owner_role TEXT, est_impact TEXT, analysis_method TEXT,
        validation_level TEXT DEFAULT 'verified',
        score_revenue_impact REAL, score_time_sensitivity REAL,
        score_strategic_alignment REAL, score_competitive_pressure REAL,
        suggested_owner TEXT, estimated_impact TEXT,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_bus (
        signal_id INTEGER, bu_id TEXT,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_validations (
        id INTEGER PRIMARY KEY, signal_id INTEGER,
        corroborating_url TEXT, corroborating_source TEXT,
        corroborating_title TEXT,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_industries (
        signal_id INTEGER, industry_id TEXT,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY, signal_id INTEGER,
        rating TEXT, comment TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY, keyword TEXT UNIQUE, active INTEGER DEFAULT 1,
        source TEXT DEFAULT 'manual', industry_id TEXT, hit_count INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn


def _insert_signal(conn, title, summary="", source="test", signal_type="competitive-threat",
                   score=7.5, status="scored", bu_ids=None):
    """Insert a signal + analysis with optional multi-BU mapping."""
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO signals (external_id, title, summary, url, source_name, source_type, collected_at, status) "
        "VALUES (?, ?, ?, ?, ?, 'rss', ?, ?)",
        (f"ext-{hash(title) % 100000}", title, summary, f"https://example.com/{hash(title) % 1000}", source, now, status),
    )
    sig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO signal_analysis (signal_id, headline, signal_type, score_composite, what_summary, quick_win) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (sig_id, title, signal_type, score, summary, "Take action"),
    )
    for bu_id in (bu_ids or ["vpg-force-sensors"]):
        conn.execute("INSERT INTO signal_bus (signal_id, bu_id) VALUES (?, ?)", (sig_id, bu_id))
    conn.commit()
    return sig_id


# ── Cross-BU Tests ─────────────────────────────────────────────────

class TestCrossBU:
    def test_find_no_cross_bu(self, tmp_path):
        from src.analyzer.cross_bu import find_cross_bu_opportunities
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Single BU signal", bu_ids=["vpg-force-sensors"])
        result = find_cross_bu_opportunities(conn)
        assert result["total"] == 0
        conn.close()

    def test_find_cross_bu_opportunity(self, tmp_path):
        from src.analyzer.cross_bu import find_cross_bu_opportunities
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Multi-BU automation signal", bu_ids=["vpg-force-sensors", "vpg-onboard-weighing"])
        result = find_cross_bu_opportunities(conn)
        assert result["total"] >= 1
        opp = result["opportunities"][0]
        assert opp["bu_count"] >= 2
        assert "did_you_know" in opp
        conn.close()

    def test_cross_bu_solution_matching(self, tmp_path):
        from src.analyzer.cross_bu import find_cross_bu_opportunities
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Steel process signal", bu_ids=["kelk", "blh-nobel"])
        result = find_cross_bu_opportunities(conn)
        assert result["total"] >= 1
        opp = result["opportunities"][0]
        assert "Metals Processing" in opp["did_you_know"]["title"]
        conn.close()

    def test_get_cross_bu_for_digest(self):
        from src.analyzer.cross_bu import get_cross_bu_for_digest
        bu_config = {"business_units": [
            {"id": "vpg-force-sensors", "name": "VPG Force Sensors"},
            {"id": "vpg-onboard-weighing", "name": "VPG Onboard Weighing"},
        ]}
        signals = [
            {"headline": "Test", "composite_score": 8.0, "signal_type": "revenue-opportunity",
             "bu_matches": [{"bu_id": "vpg-force-sensors"}, {"bu_id": "vpg-onboard-weighing"}]},
            {"headline": "Single BU", "composite_score": 7.0, "signal_type": "market-shift",
             "bu_matches": [{"bu_id": "vpg-force-sensors"}]},
        ]
        result = get_cross_bu_for_digest(signals, bu_config)
        assert len(result) == 1
        assert len(result[0]["bus"]) == 2

    def test_cross_bu_solutions_defined(self):
        from src.analyzer.cross_bu import CROSS_BU_SOLUTIONS
        assert len(CROSS_BU_SOLUTIONS) >= 5


# ── ROI Links Tests ────────────────────────────────────────────────

class TestROILinks:
    def test_get_roi_links_matching(self):
        from src.analyzer.roi_links import get_roi_links
        signal = {
            "headline": "New thickness measurement system comparison",
            "what_summary": "KELK vs X-ray TCO analysis shows advantages",
            "bu_matches": [{"bu_id": "kelk"}],
        }
        links = get_roi_links(signal)
        assert len(links) >= 1
        assert any("TCO" in l["name"] for l in links)

    def test_get_roi_links_no_match(self):
        from src.analyzer.roi_links import get_roi_links
        signal = {
            "headline": "General industry news",
            "what_summary": "Nothing specific",
            "bu_matches": [{"bu_id": "gleeble"}],
        }
        links = get_roi_links(signal)
        assert len(links) == 0

    def test_enrich_signals(self):
        from src.analyzer.roi_links import enrich_signals_with_roi
        signals = [
            {"headline": "Fleet weighing compliance update", "what_summary": "Overload fines increasing",
             "bu_matches": [{"bu_id": "vpg-onboard-weighing"}]},
            {"headline": "General news", "what_summary": "No match",
             "bu_matches": [{"bu_id": "gleeble"}]},
        ]
        enriched = enrich_signals_with_roi(signals)
        assert "roi_links" in enriched[0]
        assert "roi_links" not in enriched[1]

    def test_roi_tools_defined(self):
        from src.analyzer.roi_links import ROI_TOOLS
        assert len(ROI_TOOLS) >= 5


# ── Source Health Tests ────────────────────────────────────────────

class TestSourceHealth:
    def test_source_health_empty_db(self, tmp_path):
        from src.collector.source_health import get_source_health
        conn = _setup_db(tmp_path)
        with patch("src.collector.source_health.get_sources", return_value={"sources": [
            {"id": "test-src", "name": "Test Source", "type": "rss", "tier": 1, "active": True},
        ]}):
            result = get_source_health(conn)
        assert "sources" in result
        assert "summary" in result
        assert result["sources"][0]["status"] == "inactive"
        conn.close()

    def test_source_health_with_signals(self, tmp_path):
        from src.collector.source_health import get_source_health
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Signal from Reuters", source="Reuters")
        _insert_signal(conn, "Another Reuters signal", source="Reuters")
        with patch("src.collector.source_health.get_sources", return_value={"sources": [
            {"id": "reuters", "name": "Reuters", "type": "rss", "tier": 1, "active": True},
        ]}):
            result = get_source_health(conn)
        src = result["sources"][0]
        assert src["total_signals"] == 2
        assert src["status"] == "healthy"
        conn.close()

    def test_source_health_summary(self, tmp_path):
        from src.collector.source_health import get_source_health
        conn = _setup_db(tmp_path)
        with patch("src.collector.source_health.get_sources", return_value={"sources": [
            {"id": "s1", "name": "S1", "type": "rss", "tier": 1, "active": True},
            {"id": "s2", "name": "S2", "type": "web", "tier": 2, "active": False},
        ]}):
            result = get_source_health(conn)
        assert result["summary"]["total_sources"] == 2
        assert result["summary"]["active_sources"] == 1
        conn.close()


# ── Quick Stats Tests ──────────────────────────────────────────────

class TestQuickStats:
    def test_build_quick_stats(self):
        from src.composer.composer import _build_quick_stats
        bu_config = {"business_units": [{"id": "vpg-force-sensors", "name": "VPG Force Sensors"}]}
        signals = [
            {"signal_type": "competitive-threat", "composite_score": 8.5,
             "bu_matches": [{"bu_id": "vpg-force-sensors"}]},
            {"signal_type": "revenue-opportunity", "composite_score": 7.0,
             "bu_matches": [{"bu_id": "vpg-force-sensors"}]},
        ]
        stats = _build_quick_stats(signals, bu_config)
        assert len(stats) >= 3
        assert stats[0]["label"] == "Signals Analyzed"
        assert stats[0]["value"] == "2"

    def test_quick_stats_empty(self):
        from src.composer.composer import _build_quick_stats
        stats = _build_quick_stats([], {"business_units": []})
        assert len(stats) >= 1
        assert stats[0]["value"] == "0"


# ── Scheduler Tests ────────────────────────────────────────────────

class TestScheduler:
    def test_get_schedule_status(self):
        from src.scheduler import get_schedule_status
        with patch("src.scheduler.get_crontab", return_value=""):
            status = get_schedule_status()
        assert status["installed"] is False
        assert "default_schedule" in status

    def test_get_schedule_status_installed(self):
        from src.scheduler import get_schedule_status
        with patch("src.scheduler.get_crontab", return_value="0 4 * * 1 cd /app && python scheduler.py --now # vpg-intelligence-digest"):
            status = get_schedule_status()
        assert status["installed"] is True
        assert len(status["entries"]) == 1


# ── Digest Context Enhancement Tests ──────────────────────────────

class TestDigestContextPhase5:
    def test_context_has_cross_bu(self):
        from src.composer.composer import build_digest_context
        signals = [
            {"id": 1, "title": "Cross signal", "composite_score": 8.0, "signal_type": "revenue-opportunity",
             "headline": "Multi-BU opportunity", "what_summary": "Test", "why_it_matters": "Test",
             "quick_win": "Act", "owner_role": "Sales", "est_impact": "$1M",
             "bu_matches": [{"bu_id": "vpg-force-sensors"}, {"bu_id": "vpg-onboard-weighing"}], "sources": []},
        ]
        bu_config = {"business_units": [
            {"id": "vpg-force-sensors", "name": "VPG Force Sensors"},
            {"id": "vpg-onboard-weighing", "name": "VPG Onboard Weighing"},
        ]}
        context = build_digest_context(signals, bu_config)
        assert "cross_bu_opportunities" in context
        assert "quick_stats" in context
        assert len(context["quick_stats"]) >= 1
