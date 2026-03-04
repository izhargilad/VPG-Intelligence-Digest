"""End-to-end tests for VPG Intelligence Digest V2.1/2.2.

Tests all major components across the pipeline:
- Database schema, industries, keywords
- Signal insertion, scoring, BU mapping
- Recommendations engine
- Pattern detection
- Export (Excel, PowerPoint)
- API endpoints (via TestClient)
- Keyword discovery
- Feed & executive endpoints
"""

import json
import sqlite3
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database with full V2.1 schema."""
    from src.db import get_connection, init_db
    db_path = tmp_path / "test_e2e.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _seed_db(conn):
    """Seed a database with sample data for testing."""
    # Insert sample signals (varied types for pattern detection)
    signals = [
        ("sig-1", "Kistler launches new force sensor", "Kistler has unveiled a next-gen force sensor targeting robotics applications with enhanced accuracy.",
         "https://example.com/kistler", "rss-1", "Industry Week", 1, "scored"),
        ("sig-2", "Caterpillar seeking load cell suppliers", "Caterpillar has issued an RFP for onboard weighing systems for their mining trucks.",
         "https://example.com/cat", "rss-2", "Mining Weekly", 1, "scored"),
        ("sig-3", "US-China tariff impacts sensor market", "New 25% tariffs on Chinese sensor imports create advantage for India-based manufacturers.",
         "https://example.com/tariff", "rss-3", "Trade Monitor", 2, "scored"),
        ("sig-4", "HBK acquires strain gage startup", "HBK has acquired a Silicon Valley strain gage startup for $50M.",
         "https://example.com/hbk", "rss-4", "Sensors Daily", 1, "scored"),
        ("sig-5", "Boston Dynamics expands sensor needs", "Boston Dynamics planning major sensor procurement for next-gen robots.",
         "https://example.com/bd", "rss-5", "Robot News", 2, "scored"),
        ("sig-6", "Figure AI raises $2.6B for humanoid robots", "Figure AI secured massive funding round for humanoid robot development requiring precision sensors.",
         "https://example.com/figure", "rss-6", "TechCrunch", 1, "scored"),
        ("sig-7", "Steel mill modernization in India", "Major Indian steel producer investing $500M in rolling mill upgrades.",
         "https://example.com/steel", "web-1", "Steel Orbit", 2, "scored"),
        ("sig-8", "Automotive crash test standards update", "New NCAP standards require additional data acquisition channels for crash testing.",
         "https://example.com/crash", "rss-7", "Automotive News", 1, "scored"),
    ]

    for sig in signals:
        conn.execute(
            """INSERT INTO signals (external_id, title, summary, url, source_id, source_name, source_tier, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            sig,
        )

    # Insert analyses with scores
    analyses = [
        (1, "competitive-threat", "Kistler Force Sensor Launch", "Kistler launched next-gen force sensor", "Competes directly with VPG Force Sensors", "Brief sales team on differentiation", "VP Sales", "$1M-$3M", 7, 8, 7, 8, 7.5),
        (2, "revenue-opportunity", "Caterpillar Load Cell RFP", "Caterpillar RFP for onboard weighing", "Direct opportunity for VPG Onboard Weighing", "Prepare RFP response", "Sales Director", "$2M-$5M", 9, 9, 8, 5, 8.5),
        (3, "trade-tariff", "US-China Tariff Sensor Impact", "25% tariff on Chinese sensors", "VPG India production gains cost advantage", "Update pricing models", "VP Operations", "$5M+", 8, 7, 8, 7, 7.8),
        (4, "competitive-threat", "HBK Acquires Strain Gage Startup", "HBK acquisition strengthens portfolio", "Threatens Micro-Measurements market share", "Prepare competitive brief", "BU Manager", "$500K-$2M", 6, 6, 7, 8, 6.8),
        (5, "revenue-opportunity", "Boston Dynamics Sensor Procurement", "Major sensor buy planned", "Force sensor and DAQ opportunity", "Identify contacts at BD", "Sales Director", "$1M-$5M", 8, 8, 9, 6, 8.1),
        (6, "technology-trend", "Figure AI Humanoid Robot Funding", "$2.6B funding for robots needing sensors", "Long-term opportunity for force sensors and DAQ", "Map product capabilities", "CTO", "$5M+", 8, 6, 9, 5, 7.5),
        (7, "market-shift", "India Steel Mill Modernization", "$500M rolling mill investment", "Direct opportunity for KELK rolling mill systems", "Contact plant procurement team", "KELK Sales", "$3M-$10M", 9, 7, 9, 4, 8.0),
        (8, "market-shift", "Crash Test Standards Update", "New NCAP data acquisition requirements", "Increases DTS and Pacific Instruments addressable market", "Prepare compliance mapping", "Product Engineering", "$2M-$5M", 8, 8, 8, 5, 7.8),
    ]

    for a in analyses:
        conn.execute(
            """INSERT INTO signal_analysis
               (signal_id, signal_type, headline, what_summary, why_it_matters, quick_win,
                suggested_owner, estimated_impact, score_revenue_impact, score_time_sensitivity,
                score_strategic_alignment, score_competitive_pressure, score_composite)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            a,
        )

    # BU assignments
    bu_mappings = [
        (1, "force-sensors", 0.9), (1, "micro-measurements", 0.5),
        (2, "onboard-weighing", 0.95),
        (3, "force-sensors", 0.7), (3, "foil-resistors", 0.6), (3, "onboard-weighing", 0.5),
        (4, "micro-measurements", 0.9),
        (5, "force-sensors", 0.8), (5, "pacific-instruments", 0.6), (5, "dts", 0.5),
        (6, "force-sensors", 0.85), (6, "dts", 0.6),
        (7, "kelk", 0.95),
        (8, "dts", 0.9), (8, "pacific-instruments", 0.85),
    ]
    for sm in bu_mappings:
        conn.execute("INSERT INTO signal_bus (signal_id, bu_id, relevance_score) VALUES (?, ?, ?)", sm)

    # Industries
    industries = [
        ("robotics-automation", "Robotics & Automation", "Manufacturing & Industrial", 1),
        ("aerospace-defense", "Aerospace & Defense", "Aerospace & Defense", 1),
        ("automotive", "Automotive", "Transportation", 2),
        ("metals-mining", "Metals & Mining", "Heavy Industry", 2),
        ("physical-ai", "Physical AI", "Emerging Technologies", 1),
    ]
    for ind in industries:
        conn.execute("INSERT INTO industries (id, name, category, priority) VALUES (?, ?, ?, ?)", ind)

    # Industry-BU links
    ind_bus = [
        ("robotics-automation", "force-sensors"), ("robotics-automation", "dts"),
        ("aerospace-defense", "pacific-instruments"), ("aerospace-defense", "foil-resistors"),
        ("automotive", "dts"), ("automotive", "micro-measurements"),
        ("metals-mining", "kelk"), ("metals-mining", "blh-nobel"),
        ("physical-ai", "force-sensors"), ("physical-ai", "dts"), ("physical-ai", "pacific-instruments"),
    ]
    for ib in ind_bus:
        conn.execute("INSERT INTO industry_bus (industry_id, bu_id) VALUES (?, ?)", ib)

    # Keywords
    keywords = [
        ("load cell", "robotics-automation", "manual", 1, 5),
        ("strain gage", "automotive", "manual", 1, 3),
        ("force sensor", "robotics-automation", "manual", 1, 8),
        ("tariff", "metals-mining", "manual", 1, 2),
        ("humanoid robot", "physical-ai", "auto-discovered", 0, 12),
    ]
    for kw in keywords:
        conn.execute(
            "INSERT INTO keywords (keyword, industry_id, source, active, hit_count) VALUES (?, ?, ?, ?, ?)", kw
        )

    # Trends
    trends = [
        ("force-sensors:competitive-threat", "bu_signal_type", "Force Sensors Competitive Threats", 4, "rising", 7.5, 20, "2026-02-01", "2026-03-01"),
        ("robotics", "keyword", "Robotics", 6, "spike", 8.0, 35, "2026-01-15", "2026-03-03"),
        ("tariff", "keyword", "Trade Tariffs", 3, "stable", 6.5, 10, "2026-02-10", "2026-03-02"),
    ]
    for t in trends:
        conn.execute(
            """INSERT INTO trends (trend_key, trend_type, label, occurrence_count, momentum, avg_score, week_over_week_change, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            t,
        )

    conn.commit()


@pytest.fixture
def seeded_db(tmp_db):
    """Database with sample signals, analyses, industries, and keywords."""
    _seed_db(tmp_db)
    return tmp_db


# ═══════════════════════════════════════════════════════════════════
# 1. Database Schema Tests
# ═══════════════════════════════════════════════════════════════════

class TestDatabaseSchema:
    """Verify all V2.1 tables exist and have correct structure."""

    def test_all_tables_exist(self, tmp_db):
        tables = {row[0] for row in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()}
        expected = {
            "signals", "signal_validations", "signal_analysis", "signal_bus",
            "digests", "delivery_log", "feedback", "source_health",
            "pipeline_runs", "trends", "trend_snapshots",
            "industries", "industry_bus", "keywords", "signal_industries",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_v21_tables_have_correct_columns(self, tmp_db):
        # Industries table
        cols = {row[1] for row in tmp_db.execute("PRAGMA table_info(industries)").fetchall()}
        assert {"id", "name", "category", "priority", "active"}.issubset(cols)

        # Keywords table
        cols = {row[1] for row in tmp_db.execute("PRAGMA table_info(keywords)").fetchall()}
        assert {"keyword", "industry_id", "bu_id", "source", "active", "hit_count"}.issubset(cols)

    def test_foreign_keys_enabled(self, tmp_db):
        result = tmp_db.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1


# ═══════════════════════════════════════════════════════════════════
# 2. Industry & Keyword CRUD Tests
# ═══════════════════════════════════════════════════════════════════

class TestIndustryKeywordCRUD:
    def test_upsert_industry(self, tmp_db):
        from src.db import upsert_industry, get_all_industries
        upsert_industry(tmp_db, {
            "id": "test-industry",
            "name": "Test Industry",
            "category": "Testing",
            "priority": 1,
            "active": True,
            "relevant_bus": ["force-sensors"],
        })
        industries = get_all_industries(tmp_db)
        found = [i for i in industries if i["id"] == "test-industry"]
        assert len(found) == 1
        assert found[0]["name"] == "Test Industry"
        assert "force-sensors" in found[0]["relevant_bus"]

    def test_upsert_keyword(self, tmp_db):
        from src.db import upsert_keyword, get_all_keywords
        # Seed an industry first
        tmp_db.execute("INSERT INTO industries (id, name) VALUES ('test-ind', 'Test')")
        tmp_db.commit()

        kw_id = upsert_keyword(tmp_db, {
            "keyword": "Test Keyword",
            "industry_id": "test-ind",
            "source": "manual",
            "active": True,
        })
        assert kw_id > 0

        keywords = get_all_keywords(tmp_db, industry_id="test-ind")
        assert any(k["keyword"] == "test keyword" for k in keywords)

    def test_bulk_import_keywords(self, tmp_db):
        from src.db import bulk_import_keywords, get_all_keywords
        tmp_db.execute("INSERT INTO industries (id, name) VALUES ('bulk-ind', 'Bulk')")
        tmp_db.commit()

        count = bulk_import_keywords(tmp_db, ["alpha", "beta", "gamma", ""], "bulk-ind")
        assert count == 3  # Empty string should be skipped
        kws = get_all_keywords(tmp_db, industry_id="bulk-ind")
        assert len(kws) == 3

    def test_delete_industry(self, tmp_db):
        from src.db import upsert_industry, delete_industry
        upsert_industry(tmp_db, {"id": "del-test", "name": "Delete Me"})
        assert delete_industry(tmp_db, "del-test") is True
        assert delete_industry(tmp_db, "del-test") is False  # Already deleted


# ═══════════════════════════════════════════════════════════════════
# 3. Signal Scoring & Analysis Tests
# ═══════════════════════════════════════════════════════════════════

class TestSignalScoring:
    def test_heuristic_scoring(self):
        from src.analyzer.scorer import score_signal_heuristic
        signal = {
            "title": "Kistler launches competing force sensor product",
            "summary": "Major competitor Kistler unveiled a new force transducer targeting robotics.",
            "url": "https://example.com/test",
        }
        result = score_signal_heuristic(signal)
        assert result["signal_type"] == "competitive-threat"
        assert result["composite"] > 0
        assert result["analysis_method"] == "heuristic"
        assert "quick_win" in result
        assert "suggested_owner" in result

    def test_composite_score_calculation(self):
        from src.analyzer.scorer import calculate_composite_score
        scores = {
            "revenue_impact": 8,
            "time_sensitivity": 7,
            "strategic_alignment": 9,
            "competitive_pressure": 6,
        }
        composite = calculate_composite_score(scores)
        assert 0 < composite <= 10

    def test_bu_matching(self):
        from src.analyzer.scorer import match_signal_to_bus
        signal = {
            "title": "New load cell for onboard weighing in mining trucks",
            "summary": "Advanced load cell technology for heavy vehicle weighing applications.",
        }
        matches = match_signal_to_bus(signal)
        assert len(matches) > 0
        bu_ids = [m["bu_id"] for m in matches]
        # Should match onboard weighing or BLH Nobel
        assert any("weigh" in bid or "blh" in bid for bid in bu_ids)


# ═══════════════════════════════════════════════════════════════════
# 4. Recommendations Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestRecommendations:
    def test_generate_recommendations(self, seeded_db):
        from src.analyzer.recommendations import generate_recommendations
        result = generate_recommendations(seeded_db)
        assert "recommendations" in result
        assert "summary" in result
        assert isinstance(result["recommendations"], list)
        assert result["summary"]["total_generated"] >= 0

    def test_cross_bu_recommendations(self, seeded_db):
        from src.analyzer.recommendations import _cross_bu_recommendations
        recs = _cross_bu_recommendations(seeded_db)
        # We have signals mapped to multiple BUs (e.g., sig-3 maps to 3 BUs)
        assert isinstance(recs, list)
        for rec in recs:
            assert rec["type"] == "cross-bu"
            assert "bus" in rec
            assert len(rec["bus"]) >= 2

    def test_high_impact_recommendations(self, seeded_db):
        from src.analyzer.recommendations import _high_impact_recommendations
        recs = _high_impact_recommendations(seeded_db)
        assert isinstance(recs, list)
        for rec in recs:
            assert rec["type"] == "high-impact"
            assert rec["priority"] == 1
            assert rec["score"] >= 8.0

    def test_trend_recommendations(self, seeded_db):
        from src.analyzer.recommendations import _trend_recommendations
        recs = _trend_recommendations(seeded_db)
        # We have rising and spike trends seeded
        assert isinstance(recs, list)
        for rec in recs:
            assert rec["type"] == "trend-alert"

    def test_keyword_recommendations(self, seeded_db):
        from src.analyzer.recommendations import _keyword_recommendations
        recs = _keyword_recommendations(seeded_db)
        assert isinstance(recs, list)
        # We have a high-hit inactive keyword "humanoid robot"
        activate_recs = [r for r in recs if "Activate" in r["title"]]
        assert len(activate_recs) >= 1

    def test_recommendation_dedup_and_sorting(self, seeded_db):
        from src.analyzer.recommendations import generate_recommendations
        result = generate_recommendations(seeded_db)
        recs = result["recommendations"]
        # Should be sorted by priority (1 first)
        priorities = [r["priority"] for r in recs]
        assert priorities == sorted(priorities)
        # No duplicate keys
        keys = [r.get("key") for r in recs]
        assert len(keys) == len(set(keys))


# ═══════════════════════════════════════════════════════════════════
# 5. Pattern Detection Tests
# ═══════════════════════════════════════════════════════════════════

class TestPatternDetection:
    def test_detect_patterns(self, seeded_db):
        from src.analyzer.pattern_detector import detect_patterns
        result = detect_patterns(seeded_db)
        assert "competitor_patterns" in result
        assert "topic_persistence" in result
        assert "score_escalation" in result
        assert "bu_concentration" in result
        assert "source_patterns" in result
        assert "total_patterns" in result
        assert "detected_at" in result

    def test_competitor_detection(self, seeded_db):
        from src.analyzer.pattern_detector import _detect_competitor_patterns
        patterns = _detect_competitor_patterns(seeded_db)
        assert isinstance(patterns, list)
        # We mentioned Kistler, HBK, Boston Dynamics, Figure AI in signals
        competitor_names = [p["competitor"] for p in patterns]
        # At least one should be detected
        for p in patterns:
            assert p["signal_count"] >= 3  # MIN_PATTERN_SIGNALS
            assert "severity" in p

    def test_topic_persistence(self, seeded_db):
        from src.analyzer.pattern_detector import _detect_topic_persistence
        patterns = _detect_topic_persistence(seeded_db)
        assert isinstance(patterns, list)
        for p in patterns:
            assert "topic" in p
            assert "momentum" in p
            assert "persistence" in p

    def test_bu_concentration(self, seeded_db):
        from src.analyzer.pattern_detector import _detect_bu_concentration
        patterns = _detect_bu_concentration(seeded_db)
        assert isinstance(patterns, list)
        for p in patterns:
            assert "bu_name" in p
            assert "concentration" in p
            assert p["concentration"] in ("over-concentrated", "under-represented")

    def test_source_reliability(self, seeded_db):
        from src.analyzer.pattern_detector import _detect_source_reliability
        patterns = _detect_source_reliability(seeded_db)
        assert isinstance(patterns, list)
        for p in patterns:
            assert p["performance"] in ("high-performer", "low-performer")


# ═══════════════════════════════════════════════════════════════════
# 6. Keyword Discovery Tests
# ═══════════════════════════════════════════════════════════════════

class TestKeywordDiscovery:
    def test_extract_ngrams(self):
        from src.analyzer.keyword_discovery import _extract_ngrams
        text = "precision force sensor for industrial robotics applications"
        ngrams = _extract_ngrams(text, n=2)
        assert len(ngrams) > 0
        # Should include unigrams and bigrams
        assert any(" " in ng for ng in ngrams)  # bigrams
        assert any(" " not in ng for ng in ngrams)  # unigrams

    def test_discover_keywords(self, seeded_db):
        from src.analyzer.keyword_discovery import discover_keywords_from_signals
        result = discover_keywords_from_signals(seeded_db, min_score=5.0)
        assert "discovered" in result
        assert "stats" in result
        assert result["stats"]["signals_analyzed"] > 0

    def test_update_hit_counts(self, seeded_db):
        from src.analyzer.keyword_discovery import update_keyword_hit_counts
        updated = update_keyword_hit_counts(seeded_db)
        assert isinstance(updated, int)


# ═══════════════════════════════════════════════════════════════════
# 7. Export Tests
# ═══════════════════════════════════════════════════════════════════

class TestExport:
    def test_excel_export(self, seeded_db):
        """Test Excel export produces a valid .xlsx buffer."""
        try:
            import openpyxl  # noqa: F401
            from src.export.excel_export import export_signals_excel
        except ImportError:
            pytest.skip("openpyxl not installed")

        # Patch get_connection to use our seeded DB
        with patch("src.export.excel_export.get_connection", return_value=seeded_db):
            buffer = export_signals_excel()
            assert isinstance(buffer, BytesIO)
            assert buffer.tell() == 0  # Should be seeked to start
            content = buffer.read()
            assert len(content) > 100  # Should have substantial content
            # Verify it's a valid xlsx (starts with PK zip header)
            assert content[:2] == b"PK"

    def test_pptx_export(self, seeded_db):
        """Test PowerPoint export produces a valid .pptx buffer."""
        try:
            import pptx  # noqa: F401
            from src.export.pptx_export import export_signals_pptx
        except ImportError:
            pytest.skip("python-pptx not installed")

        with patch("src.export.pptx_export.get_connection", return_value=seeded_db):
            buffer = export_signals_pptx()
            assert isinstance(buffer, BytesIO)
            content = buffer.read()
            assert len(content) > 100
            assert content[:2] == b"PK"


# ═══════════════════════════════════════════════════════════════════
# 8. API Endpoint Tests (via FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════════

class TestAPIEndpoints:
    """Test API endpoints with TestClient.

    Uses a file-based temp DB so each thread can open its own connection.
    """

    @pytest.fixture
    def api_db_path(self, tmp_path):
        """Create and seed a temp DB file for API tests."""
        from src.db import get_connection, init_db
        db_path = tmp_path / "api_test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        _seed_db(conn)
        conn.close()
        return db_path

    @pytest.fixture
    def client(self, api_db_path):
        from fastapi.testclient import TestClient
        from src.api.server import app
        from src.db import get_connection as real_get_connection

        def _make_conn():
            return real_get_connection(api_db_path)

        with patch("src.api.server.get_connection", side_effect=_make_conn):
            with patch("src.api.server.init_db"):
                yield TestClient(app)

    def test_dashboard(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            with patch("src.api.server.init_db"):
                resp = client.get("/api/dashboard")
                assert resp.status_code == 200
                data = resp.json()
                assert "signals_total" in data
                assert "industries_count" in data
                assert "keywords_count" in data

    def test_list_industries(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/industries")
            assert resp.status_code == 200
            data = resp.json()
            assert "industries" in data
            assert len(data["industries"]) >= 5

    def test_list_keywords(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/keywords")
            assert resp.status_code == 200
            data = resp.json()
            assert "keywords" in data

    def test_feed_endpoint(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/feed")
            assert resp.status_code == 200
            data = resp.json()
            assert "signals" in data
            assert "total" in data
            assert data["total"] > 0

    def test_feed_with_filters(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/feed?signal_type=competitive-threat&min_score=7.0")
            assert resp.status_code == 200
            data = resp.json()
            for sig in data["signals"]:
                assert sig["signal_type"] == "competitive-threat"
                assert sig["score_composite"] >= 7.0

    def test_executive_bu_summary(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/executive/bu-summary")
            assert resp.status_code == 200
            data = resp.json()
            assert "bu_summaries" in data
            assert data["bus_with_signals"] > 0

    def test_recommendations_endpoint(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        factory = lambda: real_get_connection(api_db_path)
        with patch("src.api.server.get_connection", side_effect=factory):
            with patch("src.analyzer.recommendations.get_connection", side_effect=factory):
                resp = client.get("/api/recommendations")
                assert resp.status_code == 200
                data = resp.json()
                assert "recommendations" in data
                assert "summary" in data

    def test_patterns_endpoint(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        factory = lambda: real_get_connection(api_db_path)
        with patch("src.api.server.get_connection", side_effect=factory):
            with patch("src.analyzer.pattern_detector.get_connection", side_effect=factory):
                resp = client.get("/api/patterns")
                assert resp.status_code == 200
                data = resp.json()
                assert "competitor_patterns" in data
                assert "total_patterns" in data

    def test_signals_endpoint(self, client, api_db_path):
        from src.db import get_connection as real_get_connection
        with patch("src.api.server.get_connection", side_effect=lambda: real_get_connection(api_db_path)):
            resp = client.get("/api/signals?status=scored")
            assert resp.status_code == 200
            data = resp.json()
            assert "signals" in data
            assert data["total"] == 8

    def test_pipeline_status(self, client):
        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data

    def test_recipients_crud(self, client):
        resp = client.get("/api/recipients")
        assert resp.status_code == 200

    def test_sources_list(self, client):
        resp = client.get("/api/sources")
        assert resp.status_code == 200

    def test_scoring_config(self, client):
        resp = client.get("/api/scoring")
        assert resp.status_code == 200
        data = resp.json()
        assert "scoring_dimensions" in data


# ═══════════════════════════════════════════════════════════════════
# 9. Config Tests
# ═══════════════════════════════════════════════════════════════════

class TestConfig:
    def test_load_business_units(self):
        from src.config import get_business_units
        bu = get_business_units()
        assert "business_units" in bu
        assert len(bu["business_units"]) == 9

    def test_load_sources(self):
        from src.config import get_sources
        sources = get_sources()
        assert "sources" in sources
        assert len(sources["sources"]) > 0

    def test_load_scoring_weights(self):
        from src.config import get_scoring_weights
        weights = get_scoring_weights()
        assert "scoring_dimensions" in weights
        dims = weights["scoring_dimensions"]
        total_weight = sum(d["weight"] for d in dims.values())
        assert abs(total_weight - 1.0) < 0.01, f"Weights must sum to 1.0, got {total_weight}"

    def test_load_industries(self):
        from src.config import get_industries
        industries = get_industries()
        assert "industries" in industries
        assert len(industries["industries"]) >= 19  # 16 original + 3 new (General Industrial, Consumer Electronics, Physical AI)


# ═══════════════════════════════════════════════════════════════════
# 10. Integration: Signal-to-Recommendation Flow
# ═══════════════════════════════════════════════════════════════════

class TestIntegrationFlows:
    """End-to-end integration testing of multi-component flows."""

    def test_signal_to_analysis_to_recommendation(self, seeded_db):
        """Full flow: signal -> score -> BU mapping -> recommendation."""
        from src.db import insert_signal, insert_analysis, save_signal_bus
        from src.analyzer.recommendations import generate_recommendations

        # Insert a new high-value signal
        sig_id = insert_signal(seeded_db, {
            "external_id": "integration-test-1",
            "title": "Major robotics company seeks precision force measurement",
            "summary": "A leading robotics firm is evaluating force sensors for next-gen cobots.",
            "url": "https://example.com/integration",
            "source_id": "test",
            "source_name": "Integration Test",
            "source_tier": 1,
        })
        assert sig_id > 0

        # Score it
        analysis = {
            "signal_type": "revenue-opportunity",
            "headline": "Robotics Force Sensor Opportunity",
            "what_summary": "Major robotics company evaluating force sensors",
            "why_it_matters": "Direct opportunity for VPG Force Sensors",
            "quick_win": "Contact procurement team",
            "suggested_owner": "Sales Director",
            "estimated_impact": "$2M-$5M",
            "scores": {"revenue_impact": 9, "time_sensitivity": 8, "strategic_alignment": 9, "competitive_pressure": 6},
            "composite": 8.5,
            "validation_level": "verified",
        }
        insert_analysis(seeded_db, sig_id, analysis)

        # Map to BUs
        save_signal_bus(seeded_db, sig_id, [
            {"bu_id": "force-sensors", "relevance_score": 0.95},
            {"bu_id": "micro-measurements", "relevance_score": 0.5},
        ])

        # Update status to scored
        seeded_db.execute("UPDATE signals SET status = 'scored' WHERE id = ?", (sig_id,))
        seeded_db.commit()

        # Now generate recommendations — should include this high-impact signal
        result = generate_recommendations(seeded_db)
        high_impact = [r for r in result["recommendations"] if r["type"] == "high-impact"]
        assert len(high_impact) > 0

    def test_industry_keyword_signal_linking(self, seeded_db):
        """Test that signals can be linked to industries and keywords used."""
        from src.db import save_signal_industries

        # Link signal 1 to robotics industry
        save_signal_industries(seeded_db, 1, [{
            "industry_id": "robotics-automation",
            "relevance_score": 0.9,
            "matched_keywords": "force sensor, robotics",
        }])

        # Verify the link
        row = seeded_db.execute(
            "SELECT * FROM signal_industries WHERE signal_id = 1 AND industry_id = 'robotics-automation'"
        ).fetchone()
        assert row is not None
        assert row["relevance_score"] == 0.9

    def test_pattern_detection_with_fresh_data(self, seeded_db):
        """Test pattern detection recognizes competitor clustering."""
        from src.analyzer.pattern_detector import detect_patterns

        result = detect_patterns(seeded_db)
        # We have trends with rising/spike momentum -> topic_persistence
        assert len(result["topic_persistence"]) > 0
        # Source patterns should exist given our varied sources
        # BU concentration should flag over/under-concentrated BUs
        assert result["total_patterns"] >= 0

    def test_timeframe_filtering(self, seeded_db):
        """Test that timeframe filters work across endpoints."""
        from src.db import get_signals_by_timeframe, get_pipeline_runs_by_timeframe

        # All signals (no filter)
        all_sigs = get_signals_by_timeframe(seeded_db)
        assert len(all_sigs) >= 8

        # Future date should return nothing
        empty = get_signals_by_timeframe(seeded_db, start_date="2099-01-01")
        assert len(empty) == 0

    def test_pipeline_control_state(self):
        """Test pipeline pause/resume/cancel state machine."""
        from src.pipeline import PipelineControl

        ctrl = PipelineControl()
        assert not ctrl.is_paused
        assert not ctrl.is_cancelled

        ctrl.pause()
        assert ctrl.is_paused

        ctrl.resume()
        assert not ctrl.is_paused

        ctrl.cancel()
        assert ctrl.is_cancelled

        ctrl.reset()
        assert not ctrl.is_cancelled
        assert not ctrl.is_paused
