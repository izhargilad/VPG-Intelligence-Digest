"""AI-powered recommendations engine for VPG Intelligence Digest.

Generates strategic recommendations by analyzing:
- Cross-BU signal patterns (signals relevant to multiple BUs)
- Recurring themes across time periods
- High-scoring signals that deserve follow-up
- Gaps in coverage (BUs or industries with no recent signals)

Recommendations are actionable and tied to specific BUs, signal types, or trends.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime

from src.config import get_business_units, get_scoring_weights
from src.db import get_connection, get_all_industries, get_all_keywords

logger = logging.getLogger(__name__)

# Recommendation priority thresholds
HIGH_SCORE_THRESHOLD = 8.0
CROSS_BU_MIN = 2  # Minimum BUs for a cross-BU recommendation
COVERAGE_GAP_DAYS = 14  # Days without signals to flag a gap


def generate_recommendations(conn=None, max_recommendations: int = 15) -> dict:
    """Generate strategic recommendations from current signal data.

    Analyzes patterns across scored signals and produces actionable
    recommendations for each VPG business unit.

    Args:
        conn: DB connection (creates one if None).
        max_recommendations: Maximum recommendations to return.

    Returns:
        Dict with 'recommendations' list and 'summary' stats.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        recommendations = []

        # 1. Cross-BU opportunities
        recommendations.extend(_cross_bu_recommendations(conn))

        # 2. High-impact signal follow-ups
        recommendations.extend(_high_impact_recommendations(conn))

        # 3. Coverage gap alerts
        recommendations.extend(_coverage_gap_recommendations(conn))

        # 4. Trend-based recommendations
        recommendations.extend(_trend_recommendations(conn))

        # 5. Keyword performance recommendations
        recommendations.extend(_keyword_recommendations(conn))

        # De-duplicate and prioritize
        seen_keys = set()
        unique = []
        for rec in recommendations:
            key = rec.get("key", rec["title"])
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(rec)

        # Sort by priority (1=critical, 2=high, 3=medium)
        unique.sort(key=lambda r: (r.get("priority", 3), -r.get("score", 0)))
        final = unique[:max_recommendations]

        return {
            "recommendations": final,
            "summary": {
                "total_generated": len(unique),
                "returned": len(final),
                "by_type": dict(Counter(r["type"] for r in final)),
                "by_priority": dict(Counter(r["priority"] for r in final)),
                "generated_at": datetime.now().isoformat(),
            },
        }

    finally:
        if close_conn:
            conn.close()


def _cross_bu_recommendations(conn) -> list[dict]:
    """Find signals relevant to multiple BUs — collaboration opportunities."""
    rows = conn.execute("""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               GROUP_CONCAT(sb.bu_id) as bus
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        JOIN signal_bus sb ON s.id = sb.signal_id
        WHERE s.status IN ('scored', 'published')
        GROUP BY s.id
        HAVING COUNT(DISTINCT sb.bu_id) >= ?
        ORDER BY sa.score_composite DESC
        LIMIT 10
    """, (CROSS_BU_MIN,)).fetchall()

    bu_config = get_business_units()
    bu_names = {bu["id"]: bu.get("short_name", bu["name"])
                for bu in bu_config.get("business_units", [])}

    recs = []
    for row in rows:
        bus = row[4].split(",") if row[4] else []
        bu_labels = [bu_names.get(b, b) for b in bus]
        recs.append({
            "type": "cross-bu",
            "priority": 2 if row[3] >= HIGH_SCORE_THRESHOLD else 3,
            "title": f"Cross-BU Opportunity: {row[1][:80]}",
            "description": (
                f"This {row[2].replace('-', ' ')} signal (score {row[3]:.1f}) is relevant to "
                f"{', '.join(bu_labels)}. A coordinated response across these BUs could "
                f"amplify impact and avoid duplicated effort."
            ),
            "action": "Schedule a cross-BU briefing to align on response strategy.",
            "signal_id": row[0],
            "bus": bus,
            "score": row[3] or 0,
            "key": f"cross-bu-{row[0]}",
        })

    return recs


def _high_impact_recommendations(conn) -> list[dict]:
    """Flag high-scoring signals that need immediate action."""
    rows = conn.execute("""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.quick_win, sa.suggested_owner, sa.estimated_impact
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND sa.score_composite >= ?
        ORDER BY sa.score_composite DESC
        LIMIT 5
    """, (HIGH_SCORE_THRESHOLD,)).fetchall()

    recs = []
    for row in rows:
        recs.append({
            "type": "high-impact",
            "priority": 1,
            "title": f"Priority Action: {row[1][:80]}",
            "description": (
                f"Score {row[3]:.1f} — {row[2].replace('-', ' ').title()}. "
                f"Estimated impact: {row[6] or 'TBD'}."
            ),
            "action": row[4] or "Review and act on this signal immediately.",
            "owner": row[5] or "BU Manager",
            "signal_id": row[0],
            "score": row[3] or 0,
            "key": f"high-impact-{row[0]}",
        })

    return recs


def _coverage_gap_recommendations(conn) -> list[dict]:
    """Identify BUs or industries with no recent signals."""
    bu_config = get_business_units()
    all_bus = {bu["id"]: bu.get("short_name", bu["name"])
               for bu in bu_config.get("business_units", []) if bu.get("active", True)}

    # BUs with recent signals
    active_bus = conn.execute("""
        SELECT DISTINCT sb.bu_id
        FROM signal_bus sb
        JOIN signals s ON sb.signal_id = s.id
        WHERE s.status IN ('scored', 'published')
          AND s.collected_at >= datetime('now', ?)
    """, (f"-{COVERAGE_GAP_DAYS} days",)).fetchall()
    active_set = {row[0] for row in active_bus}

    recs = []
    for bu_id, bu_name in all_bus.items():
        if bu_id not in active_set:
            recs.append({
                "type": "coverage-gap",
                "priority": 3,
                "title": f"Coverage Gap: No recent signals for {bu_name}",
                "description": (
                    f"{bu_name} has had no scored signals in the past {COVERAGE_GAP_DAYS} days. "
                    f"This may indicate a gap in source coverage or keyword configuration."
                ),
                "action": (
                    f"Review source configuration and keywords for {bu_name}. "
                    f"Consider adding industry-specific RSS feeds or expanding keyword lists."
                ),
                "bu_id": bu_id,
                "score": 0,
                "key": f"gap-{bu_id}",
            })

    return recs


def _trend_recommendations(conn) -> list[dict]:
    """Generate recommendations from trend momentum changes."""
    rows = conn.execute("""
        SELECT trend_key, label, momentum, occurrence_count,
               week_over_week_change, avg_score
        FROM trends
        WHERE momentum IN ('spike', 'rising')
          AND occurrence_count >= 3
        ORDER BY
            CASE momentum WHEN 'spike' THEN 1 WHEN 'rising' THEN 2 END,
            avg_score DESC
        LIMIT 5
    """).fetchall()

    recs = []
    for row in rows:
        momentum = row[2]
        priority = 1 if momentum == "spike" else 2
        recs.append({
            "type": "trend-alert",
            "priority": priority,
            "title": f"{'Spike' if momentum == 'spike' else 'Rising'} Trend: {row[1]}",
            "description": (
                f"'{row[1]}' has {'spiked' if momentum == 'spike' else 'been rising'} "
                f"({row[4]:+.0f}% WoW) with {row[3]} signals at avg score {row[5]:.1f}. "
                f"This pattern suggests increasing strategic relevance."
            ),
            "action": (
                "Investigate root cause of this trend. Prepare a briefing for "
                "affected BU leadership with recommended actions."
            ),
            "trend_key": row[0],
            "score": row[5] or 0,
            "key": f"trend-{row[0]}",
        })

    return recs


def _keyword_recommendations(conn) -> list[dict]:
    """Recommend keyword adjustments based on performance."""
    recs = []

    # High-performing keywords (lots of hits, should be priority)
    top_kws = conn.execute("""
        SELECT keyword, hit_count, industry_id, active
        FROM keywords
        WHERE hit_count >= 10
          AND active = 0
        ORDER BY hit_count DESC
        LIMIT 3
    """).fetchall()

    for kw in top_kws:
        recs.append({
            "type": "keyword-action",
            "priority": 3,
            "title": f"Activate High-Performing Keyword: '{kw[0]}'",
            "description": (
                f"The keyword '{kw[0]}' has matched {kw[1]} signals but is currently inactive. "
                f"Activating it would improve signal coverage."
            ),
            "action": f"Review and activate the keyword '{kw[0]}' in the Keywords management UI.",
            "score": 0,
            "key": f"kw-activate-{kw[0]}",
        })

    # Zero-hit keywords that are active (may be too specific)
    zero_kws = conn.execute("""
        SELECT COUNT(*) FROM keywords WHERE hit_count = 0 AND active = 1
    """).fetchone()[0]

    if zero_kws > 10:
        recs.append({
            "type": "keyword-action",
            "priority": 3,
            "title": f"Review {zero_kws} Zero-Hit Active Keywords",
            "description": (
                f"There are {zero_kws} active keywords that have never matched a signal. "
                f"These may be too specific, misspelled, or targeting sources not in the feed."
            ),
            "action": "Review zero-hit keywords in the Keywords UI and deactivate or refine them.",
            "score": 0,
            "key": "kw-zero-hits",
        })

    return recs
