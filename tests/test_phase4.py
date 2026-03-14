"""Tests for Phase 4 features: battle cards, customer triggers, keyword expansion,
feedback-driven scoring integration, and digest template enhancements."""

import sqlite3
from datetime import datetime, timedelta
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
        collected_at TEXT, status TEXT DEFAULT 'new'
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_analysis (
        id INTEGER PRIMARY KEY, signal_id INTEGER,
        headline TEXT, signal_type TEXT, score_composite REAL,
        what_summary TEXT, why_it_matters TEXT, quick_win TEXT,
        owner_role TEXT, est_impact TEXT, analysis_method TEXT,
        FOREIGN KEY(signal_id) REFERENCES signals(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_bus (
        signal_id INTEGER, bu_id TEXT,
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
                   score=7.5, status="scored", customer_name=None):
    """Insert a signal + analysis for testing."""
    t = title if not customer_name else f"{customer_name} {title}"
    s = summary if not customer_name else f"{customer_name} {summary}"
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO signals (external_id, title, summary, url, source_name, source_type, collected_at, status) "
        "VALUES (?, ?, ?, ?, ?, 'rss', ?, ?)",
        (f"ext-{hash(t) % 10000}", t, s, f"https://example.com/{hash(t) % 1000}", source, now, status),
    )
    sig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO signal_analysis (signal_id, headline, signal_type, score_composite, what_summary, quick_win) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (sig_id, t, signal_type, score, s, "Take action now"),
    )
    conn.commit()
    return sig_id


def _insert_feedback(conn, signal_id, rating="up"):
    """Insert feedback for a signal."""
    conn.execute(
        "INSERT INTO feedback (signal_id, rating, created_at) VALUES (?, ?, ?)",
        (signal_id, rating, datetime.now().isoformat()),
    )
    conn.commit()


# ── Battle Cards Tests ─────────────────────────────────────────────

class TestBattleCards:
    def test_list_competitors(self):
        from src.analyzer.battle_cards import list_competitors
        competitors = list_competitors()
        assert len(competitors) == 5
        names = [c["name"] for c in competitors]
        assert "Zemic" in names
        assert "Kistler Group" in names

    def test_generate_battle_card_known(self, tmp_path):
        from src.analyzer.battle_cards import generate_battle_card
        conn = _setup_db(tmp_path)
        card = generate_battle_card("hbk", conn)
        assert card["competitor"] == "HBK (Hottinger Bruel & Kjaer)"
        assert "vpg_advantages" in card
        assert "profile" in card
        assert "counter_messaging" in card
        assert len(card["counter_messaging"]) >= 1
        conn.close()

    def test_generate_battle_card_unknown(self, tmp_path):
        from src.analyzer.battle_cards import generate_battle_card
        conn = _setup_db(tmp_path)
        result = generate_battle_card("nonexistent", conn)
        assert "error" in result
        conn.close()

    def test_generate_all_battle_cards(self, tmp_path):
        from src.analyzer.battle_cards import generate_all_battle_cards
        conn = _setup_db(tmp_path)
        result = generate_all_battle_cards(conn)
        assert result["total_competitors"] == 5
        assert "battle_cards" in result
        assert "hbk" in result["battle_cards"]
        assert "zemic" in result["battle_cards"]
        conn.close()

    def test_battle_card_with_signals(self, tmp_path):
        from src.analyzer.battle_cards import generate_battle_card
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "HBK launches new DAQ system", "HBK competitive move",
                       signal_type="competitive-threat", score=8.0)
        card = generate_battle_card("hbk", conn)
        assert card["summary"]["total_signals"] >= 1
        assert len(card["recent_intelligence"]) >= 1
        conn.close()

    def test_signal_patterns_analysis(self):
        from src.analyzer.battle_cards import _analyze_signal_patterns
        signals = [
            {"signal_type": "competitive-threat", "score": 8, "date": datetime.now().strftime("%Y-%m-%d")},
            {"signal_type": "competitive-threat", "score": 7, "date": datetime.now().strftime("%Y-%m-%d")},
            {"signal_type": "technology-trend", "score": 6, "date": "2024-01-01"},
        ]
        patterns = _analyze_signal_patterns(signals)
        assert patterns["dominant_type"] == "competitive-threat"
        assert patterns["activity_level"] == "low"
        assert patterns["total_signals"] == 3


# ── Customer Triggers Tests ────────────────────────────────────────

class TestCustomerTriggers:
    def test_detect_no_triggers(self, tmp_path):
        from src.analyzer.customer_triggers import detect_customer_triggers
        conn = _setup_db(tmp_path)
        result = detect_customer_triggers(conn)
        assert result["total_triggers"] == 0
        assert result["customers_with_triggers"] == 0
        conn.close()

    def test_detect_expansion_trigger(self, tmp_path):
        from src.analyzer.customer_triggers import detect_customer_triggers
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Caterpillar announces new facility expansion in Texas",
                       "Caterpillar groundbreaking for new manufacturing plant",
                       signal_type="revenue-opportunity", score=8.5)
        result = detect_customer_triggers(conn)
        assert result["total_triggers"] >= 1
        cat_triggers = [t for t in result["triggers"] if t["customer"] == "Caterpillar"]
        assert len(cat_triggers) == 1
        assert cat_triggers[0]["triggers"][0]["trigger_type"] == "facility-expansion"
        conn.close()

    def test_detect_acquisition_trigger(self, tmp_path):
        from src.analyzer.customer_triggers import detect_customer_triggers
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Boeing acquires sensor startup",
                       "Boeing acquisition expands sensor portfolio",
                       signal_type="customer-intelligence", score=7.0)
        result = detect_customer_triggers(conn)
        boeing = [t for t in result["triggers"] if t["customer"] == "Boeing"]
        assert len(boeing) == 1
        assert boeing[0]["triggers"][0]["trigger_type"] == "acquisition"
        conn.close()

    def test_upsell_brief_generation(self, tmp_path):
        from src.analyzer.customer_triggers import detect_customer_triggers
        conn = _setup_db(tmp_path)
        _insert_signal(conn, "Tesla hiring surge in manufacturing engineering",
                       "Tesla recruiting hundreds of engineers",
                       signal_type="customer-intelligence", score=6.5)
        result = detect_customer_triggers(conn)
        tesla = [t for t in result["triggers"] if t["customer"] == "Tesla"]
        assert len(tesla) == 1
        brief = tesla[0]["upsell_brief"]
        assert brief["priority"] in ("high", "medium")
        assert len(brief["recommended_actions"]) >= 1
        conn.close()

    def test_classify_trigger_types(self):
        from src.analyzer.customer_triggers import _classify_trigger
        assert _classify_trigger("new facility opening") == "facility-expansion"
        assert _classify_trigger("product launch event") == "product-launch"
        assert _classify_trigger("company hiring engineers") == "hiring-surge"
        assert _classify_trigger("capital expenditure increase") == "capex-increase"
        assert _classify_trigger("acquires competitor") == "acquisition"
        assert _classify_trigger("regular business news") is None


# ── Keyword Expansion Tests ────────────────────────────────────────

class TestKeywordExpansion:
    def test_expand_no_feedback(self, tmp_path):
        from src.feedback.keyword_expansion import expand_keywords_from_feedback
        conn = _setup_db(tmp_path)
        result = expand_keywords_from_feedback(conn, dry_run=True)
        assert result["summary"]["keywords_activated"] == 0
        assert result["summary"]["keywords_deactivated"] == 0
        conn.close()

    def test_activate_keyword_from_positive_feedback(self, tmp_path):
        from src.feedback.keyword_expansion import expand_keywords_from_feedback
        conn = _setup_db(tmp_path)
        # Insert inactive keyword
        conn.execute("INSERT INTO keywords (keyword, active, source) VALUES ('robotics', 0, 'discovered')")
        conn.commit()
        # Insert signals mentioning the keyword with positive feedback
        for i in range(6):
            sig_id = _insert_signal(conn, f"Robotics market update {i}", f"robotics automation trend {i}")
            _insert_feedback(conn, sig_id, "up")
        result = expand_keywords_from_feedback(conn, dry_run=True)
        # Should suggest activation
        assert result["dry_run"] is True
        conn.close()

    def test_deactivate_keyword_from_negative_feedback(self, tmp_path):
        from src.feedback.keyword_expansion import expand_keywords_from_feedback
        conn = _setup_db(tmp_path)
        # Insert active keyword
        conn.execute("INSERT INTO keywords (keyword, active, source) VALUES ('cryptocurrency', 1, 'discovered')")
        conn.commit()
        # Insert signals mentioning keyword with negative feedback
        for i in range(6):
            sig_id = _insert_signal(conn, f"Cryptocurrency news {i}", f"cryptocurrency blockchain {i}")
            _insert_feedback(conn, sig_id, "down")
        result = expand_keywords_from_feedback(conn, dry_run=True)
        assert result["dry_run"] is True
        conn.close()

    def test_extract_candidates(self, tmp_path):
        from src.feedback.keyword_expansion import _extract_keyword_candidates
        conn = _setup_db(tmp_path)
        # Insert positively-rated signals with repeated terms
        for i in range(5):
            sig_id = _insert_signal(conn, f"Advanced materials testing grows {i}",
                                    f"Thermal simulation equipment demand rises {i}")
            _insert_feedback(conn, sig_id, "up")
        candidates = _extract_keyword_candidates(conn)
        # Should find some bigram/trigram candidates
        assert isinstance(candidates, list)
        conn.close()


# ── Feedback Scoring Integration Tests ─────────────────────────────

class TestFeedbackScoringIntegration:
    def test_get_score_multiplier_no_feedback(self, tmp_path):
        from src.feedback.scoring_refinement import get_score_multiplier
        conn = _setup_db(tmp_path)
        m = get_score_multiplier("competitive-threat", "reuters", "vpg-force-sensors", conn)
        assert m == 1.0  # No feedback = no adjustment
        conn.close()

    def test_get_score_multiplier_with_feedback(self, tmp_path):
        from src.feedback.scoring_refinement import get_score_multiplier
        conn = _setup_db(tmp_path)
        # Insert enough feedback to trigger adjustments
        for i in range(6):
            sig_id = _insert_signal(conn, f"Test signal {i}", signal_type="competitive-threat")
            conn.execute("INSERT INTO signal_bus (signal_id, bu_id) VALUES (?, 'vpg-force-sensors')", (sig_id,))
            _insert_feedback(conn, sig_id, "up")
        conn.commit()
        m = get_score_multiplier("competitive-threat", "test", "vpg-force-sensors", conn)
        # Should be >= 1.0 since all feedback is positive
        assert m >= 1.0
        conn.close()

    def test_multiplier_bounds(self, tmp_path):
        from src.feedback.scoring_refinement import get_score_multiplier
        conn = _setup_db(tmp_path)
        for i in range(10):
            sig_id = _insert_signal(conn, f"Bad signal {i}", signal_type="revenue-opportunity")
            conn.execute("INSERT INTO signal_bus (signal_id, bu_id) VALUES (?, 'kelk')", (sig_id,))
            _insert_feedback(conn, sig_id, "down")
        conn.commit()
        m = get_score_multiplier("revenue-opportunity", "test", "kelk", conn)
        assert 0.7 <= m <= 1.3
        conn.close()


# ── Digest Template Enhancement Tests ──────────────────────────────

class TestDigestEnhancements:
    def test_digest_context_has_competitive_signals(self, tmp_path):
        from src.composer.composer import build_digest_context
        signals = [
            {"id": 1, "title": "HBK move", "composite_score": 8.0, "signal_type": "competitive-threat",
             "headline": "HBK launches new product", "what_summary": "Test", "why_it_matters": "Test",
             "quick_win": "Act now", "owner_role": "Sales", "est_impact": "$1M",
             "bu_matches": [{"bu_id": "vpg-force-sensors"}], "sources": []},
            {"id": 2, "title": "Trade news", "composite_score": 7.0, "signal_type": "trade-tariff",
             "headline": "New tariff on Chinese sensors", "what_summary": "Test", "why_it_matters": "Test",
             "quick_win": "Act now", "owner_role": "Sales", "est_impact": "$500K",
             "bu_matches": [{"bu_id": "blh-nobel"}], "sources": []},
        ]
        bu_config = {"business_units": [
            {"id": "vpg-force-sensors", "name": "VPG Force Sensors"},
            {"id": "blh-nobel", "name": "BLH Nobel"},
        ]}
        context = build_digest_context(signals, bu_config)
        assert "competitive_signals" in context
        assert "trade_signals" in context
        assert len(context["competitive_signals"]) == 1
        assert len(context["trade_signals"]) == 1
