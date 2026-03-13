"""India Production Advantage Monitor for VPG Intelligence Digest.

Actively monitors and generates intelligence around VPG's India
manufacturing competitive advantage:

- US-China tariff updates creating India production advantages
- India manufacturing policy changes (PLI schemes, duty structures)
- Competitor supply chain vulnerabilities from China dependency
- Customer reshoring/nearshoring announcements
- India trade agreement developments

Each relevant signal includes talking points for sales enablement.
"""

import logging
from collections import defaultdict
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Keywords for India advantage monitoring
INDIA_KEYWORDS = [
    "india manufacturing", "make in india", "PLI scheme",
    "india production", "india factory", "india plant",
    "india supply chain", "india trade", "india tariff",
    "india export", "india duty",
]

CHINA_RISK_KEYWORDS = [
    "china tariff", "us-china trade", "china supply chain",
    "china sanctions", "china ban", "decoupling",
    "reshoring", "nearshoring", "friend-shoring",
    "supply chain diversification", "china risk",
    "china dependency", "china manufacturing risk",
]

RESHORING_KEYWORDS = [
    "reshoring", "nearshoring", "onshoring",
    "supply chain resilience", "de-risking",
    "manufacturing relocation", "alternative sourcing",
]

# Standard talking points for sales enablement
TALKING_POINTS = {
    "tariff_advantage": {
        "title": "Tariff Advantage",
        "point": "VPG's India manufacturing hub avoids US-China tariffs entirely. While competitors face 25-60% import duties on China-sourced components, VPG's India production offers duty-free or preferential access under US-India trade arrangements.",
        "use_when": "Customer is comparing China-sourced alternatives",
    },
    "supply_chain_resilience": {
        "title": "Supply Chain Resilience",
        "point": "VPG's India production provides supply chain resilience independent of China disruptions. Recent geopolitical tensions, COVID-era shutdowns, and trade policy shifts have exposed risks of single-source China dependency.",
        "use_when": "Customer is concerned about supply chain reliability",
    },
    "cost_competitiveness": {
        "title": "Cost Competitiveness",
        "point": "India's competitive labor costs combined with VPG's advanced manufacturing capabilities deliver price-performance advantages vs. Western-manufactured alternatives without the tariff risk of China-sourced products.",
        "use_when": "Pricing discussions or competitive bids",
    },
    "quality_with_value": {
        "title": "Quality + Value",
        "point": "VPG India facilities maintain the same ISO quality standards as all VPG global operations, with the added benefit of competitive manufacturing costs and favorable trade conditions.",
        "use_when": "Customer needs quality assurance alongside competitive pricing",
    },
    "government_incentives": {
        "title": "Government Incentives",
        "point": "India's Production Linked Incentive (PLI) scheme and favorable FDI policies support precision manufacturing growth, ensuring VPG's continued investment and capacity expansion in India.",
        "use_when": "Discussing long-term supply partnership",
    },
}


def analyze_india_signals(conn=None) -> dict:
    """Analyze all signals for India production advantage relevance.

    Returns:
        Dict with categorized India-relevant signals, talking points,
        and competitor vulnerability assessment.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        india_signals = _find_india_signals(conn)
        china_risk_signals = _find_china_risk_signals(conn)
        reshoring_signals = _find_reshoring_signals(conn)
        competitor_vulnerabilities = _assess_competitor_vulnerabilities(conn)

        all_signals = india_signals + china_risk_signals + reshoring_signals
        # Deduplicate
        seen = set()
        unique = []
        for s in all_signals:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique.append(s)

        return {
            "india_signals": india_signals,
            "china_risk_signals": china_risk_signals,
            "reshoring_signals": reshoring_signals,
            "competitor_vulnerabilities": competitor_vulnerabilities,
            "talking_points": list(TALKING_POINTS.values()),
            "summary": {
                "total_relevant_signals": len(unique),
                "india_specific": len(india_signals),
                "china_risk": len(china_risk_signals),
                "reshoring": len(reshoring_signals),
                "competitors_exposed": len(competitor_vulnerabilities),
                "analyzed_at": datetime.now().isoformat(),
            },
        }

    finally:
        if close_conn:
            conn.close()


def _find_signals_by_keywords(conn, keywords: list[str], limit: int = 20) -> list[dict]:
    """Find scored signals matching any of the given keywords."""
    conditions = " OR ".join(
        "(LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)"
        for _ in keywords
    )
    params = []
    for kw in keywords:
        pattern = f"%{kw.lower()}%"
        params.extend([pattern, pattern])

    rows = conn.execute(f"""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.what_summary, sa.why_it_matters, sa.quick_win,
               s.url, s.source_name, s.collected_at,
               GROUP_CONCAT(DISTINCT sb.bu_id) as bus
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        LEFT JOIN signal_bus sb ON s.id = sb.signal_id
        WHERE s.status IN ('scored', 'published')
          AND ({conditions})
        GROUP BY s.id
        ORDER BY sa.score_composite DESC
        LIMIT ?
    """, params + [limit]).fetchall()

    return [dict(r) for r in rows]


def _find_india_signals(conn) -> list[dict]:
    """Find signals directly related to India manufacturing."""
    signals = _find_signals_by_keywords(conn, INDIA_KEYWORDS)
    for sig in signals:
        sig["india_category"] = "india-direct"
        sig["sales_talking_point"] = TALKING_POINTS["government_incentives"]["point"]
    return signals


def _find_china_risk_signals(conn) -> list[dict]:
    """Find signals about China trade/supply chain risks."""
    signals = _find_signals_by_keywords(conn, CHINA_RISK_KEYWORDS)
    for sig in signals:
        sig["india_category"] = "china-risk"
        sig["sales_talking_point"] = TALKING_POINTS["tariff_advantage"]["point"]
    return signals


def _find_reshoring_signals(conn) -> list[dict]:
    """Find signals about reshoring/nearshoring trends."""
    signals = _find_signals_by_keywords(conn, RESHORING_KEYWORDS)
    for sig in signals:
        sig["india_category"] = "reshoring"
        sig["sales_talking_point"] = TALKING_POINTS["supply_chain_resilience"]["point"]
    return signals


def _assess_competitor_vulnerabilities(conn) -> list[dict]:
    """Assess which competitors may be vulnerable due to China dependency."""
    # Known competitors with China manufacturing exposure
    CHINA_DEPENDENT_COMPETITORS = {
        "Zemic": "Primary manufacturing in China",
        "NMB": "Significant China manufacturing footprint",
        "Flintec": "China-based production facility",
        "Sunrise Instruments": "China-headquartered manufacturer",
        "Omega": "Some product lines sourced from China",
    }

    vulnerabilities = []
    for comp, exposure in CHINA_DEPENDENT_COMPETITORS.items():
        # Check for recent signals about this competitor
        rows = conn.execute("""
            SELECT COUNT(*) as cnt,
                   AVG(sa.score_composite) as avg_score
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
              AND s.collected_at >= datetime('now', '-30 days')
        """, (f"%{comp.lower()}%", f"%{comp.lower()}%")).fetchone()

        recent_count = rows[0] if rows else 0
        avg_score = rows[1] if rows and rows[1] else 0

        vulnerabilities.append({
            "competitor": comp,
            "china_exposure": exposure,
            "recent_signal_count": recent_count,
            "avg_signal_score": round(avg_score, 1),
            "vulnerability_level": (
                "high" if "Primary" in exposure or "headquartered" in exposure
                else "medium"
            ),
            "vpg_advantage": (
                f"VPG India production offers tariff-free alternative to {comp}'s "
                f"China-sourced products. {exposure}."
            ),
        })

    return vulnerabilities


def get_india_talking_points_for_signal(signal_id: int, conn=None) -> dict:
    """Get India-specific talking points for a particular signal.

    Returns relevant talking points based on the signal's content and type.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        row = conn.execute("""
            SELECT s.title, s.summary, sa.signal_type
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.id = ?
        """, (signal_id,)).fetchone()

        if not row:
            return {"error": f"Signal {signal_id} not found"}

        text = f"{row[0]} {row[1] or ''}".lower()
        relevant_points = []

        # Match talking points based on content
        if any(kw in text for kw in ["tariff", "duty", "import tax"]):
            relevant_points.append(TALKING_POINTS["tariff_advantage"])
        if any(kw in text for kw in ["supply chain", "disruption", "shortage"]):
            relevant_points.append(TALKING_POINTS["supply_chain_resilience"])
        if any(kw in text for kw in ["cost", "price", "competitive", "bid"]):
            relevant_points.append(TALKING_POINTS["cost_competitiveness"])
        if any(kw in text for kw in ["quality", "iso", "certification"]):
            relevant_points.append(TALKING_POINTS["quality_with_value"])
        if any(kw in text for kw in ["india", "pli", "government", "incentive"]):
            relevant_points.append(TALKING_POINTS["government_incentives"])

        # If no specific match, provide general points based on signal type
        if not relevant_points:
            if row[2] == "trade-tariff":
                relevant_points = [TALKING_POINTS["tariff_advantage"], TALKING_POINTS["supply_chain_resilience"]]
            elif row[2] == "competitive-threat":
                relevant_points = [TALKING_POINTS["cost_competitiveness"], TALKING_POINTS["tariff_advantage"]]
            else:
                relevant_points = [TALKING_POINTS["supply_chain_resilience"]]

        return {
            "signal_id": signal_id,
            "talking_points": relevant_points,
        }

    finally:
        if close_conn:
            conn.close()
