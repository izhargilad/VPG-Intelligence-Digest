"""Auto-updated competitive battle cards for VPG Intelligence Digest.

Maintains running competitive positioning documents that are automatically
updated when new competitor intelligence is detected. Each battle card
contains:
- Competitor overview and recent activity
- VPG competitive advantages
- Pricing/positioning differentiators
- Recent signal intelligence
- Recommended counter-messaging

Battle cards are stored in the database and versioned.
"""

import json
import logging
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Competitor profiles with positioning data
COMPETITOR_PROFILES = {
    "hbk": {
        "name": "HBK (Hottinger Bruel & Kjaer)",
        "aliases": ["HBK", "Hottinger", "Bruel", "HBM"],
        "segments": ["Test & Measurement", "Sensors", "DAQ"],
        "strengths": ["Brand recognition", "Broad product portfolio", "Software ecosystem"],
        "weaknesses": ["Premium pricing", "Complex sales process", "European-centric support"],
        "vpg_advantages": [
            "More competitive pricing with India manufacturing",
            "Superior precision in foil technology",
            "Faster delivery and dedicated application engineering",
        ],
        "target_bus": ["vpg-force-sensors", "micro-measurements", "pacific-instruments"],
    },
    "kistler": {
        "name": "Kistler Group",
        "aliases": ["Kistler"],
        "segments": ["Dynamic measurement", "Process monitoring", "Vehicle testing"],
        "strengths": ["Piezoelectric expertise", "Automotive OEM relationships", "Process monitoring"],
        "weaknesses": ["Limited static measurement", "Higher price point", "Narrower product range"],
        "vpg_advantages": [
            "Broader sensor technology portfolio (strain gage + force + resistive)",
            "Better price-performance ratio",
            "India production for tariff-free pricing advantage",
        ],
        "target_bus": ["vpg-force-sensors", "dts", "micro-measurements"],
    },
    "zemic": {
        "name": "Zemic",
        "aliases": ["Zemic"],
        "segments": ["Load cells", "Weighing components"],
        "strengths": ["Low cost", "High volume capability"],
        "weaknesses": ["China tariff exposure", "Quality perception", "Limited application support"],
        "vpg_advantages": [
            "India manufacturing avoids China tariffs (25-60% cost advantage)",
            "Superior precision and long-term stability",
            "Full application engineering and calibration support",
        ],
        "target_bus": ["vpg-force-sensors", "blh-nobel"],
    },
    "tt-electronics": {
        "name": "TT Electronics",
        "aliases": ["TT Electronics", "TT"],
        "segments": ["Resistors", "Sensors", "Power solutions"],
        "strengths": ["Vertically integrated", "Defense certifications"],
        "weaknesses": ["Smaller sensor portfolio", "Less precision focus"],
        "vpg_advantages": [
            "Z1-Foil technology — unmatched precision and stability",
            "Deeper expertise in precision measurement applications",
            "Broader force sensor and strain gage portfolio",
        ],
        "target_bus": ["vpg-foil-resistors", "vpg-force-sensors"],
    },
    "rice-lake": {
        "name": "Rice Lake Weighing Systems",
        "aliases": ["Rice Lake"],
        "segments": ["Industrial weighing", "Vehicle scales", "Process weighing"],
        "strengths": ["US-based", "Strong distribution", "Complete weighing solutions"],
        "weaknesses": ["Less precision-focused", "Limited sensor technology", "No force measurement"],
        "vpg_advantages": [
            "Superior load cell precision and repeatability",
            "Broader sensor technology portfolio beyond weighing",
            "India manufacturing for competitive global pricing",
        ],
        "target_bus": ["vpg-force-sensors", "blh-nobel", "vpg-onboard-weighing"],
    },
}


def generate_battle_card(competitor_key: str, conn=None) -> dict:
    """Generate or update a competitive battle card.

    Args:
        competitor_key: Key from COMPETITOR_PROFILES
        conn: DB connection

    Returns:
        Complete battle card dict.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        profile = COMPETITOR_PROFILES.get(competitor_key)
        if not profile:
            return {"error": f"Unknown competitor: {competitor_key}"}

        # Find recent signals about this competitor
        recent_signals = _find_competitor_signals(conn, profile)

        # Classify signal patterns
        signal_patterns = _analyze_signal_patterns(recent_signals)

        # Generate counter-messaging
        counter_messaging = _generate_counter_messages(profile, recent_signals)

        bu_config = get_business_units()
        bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}
        affected_bus = [bu_names.get(b, b) for b in profile.get("target_bus", [])]

        return {
            "competitor": profile["name"],
            "competitor_key": competitor_key,
            "last_updated": datetime.now().isoformat(),
            "profile": {
                "segments": profile["segments"],
                "strengths": profile["strengths"],
                "weaknesses": profile["weaknesses"],
            },
            "vpg_advantages": profile["vpg_advantages"],
            "affected_bus": affected_bus,
            "recent_intelligence": recent_signals[:10],
            "signal_patterns": signal_patterns,
            "counter_messaging": counter_messaging,
            "summary": {
                "total_signals": len(recent_signals),
                "avg_score": round(
                    sum(s.get("score", 0) for s in recent_signals) / max(len(recent_signals), 1), 1
                ),
                "signal_trend": signal_patterns.get("trend", "stable"),
            },
        }

    finally:
        if close_conn:
            conn.close()


def generate_all_battle_cards(conn=None) -> dict:
    """Generate battle cards for all tracked competitors."""
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        cards = {}
        for key in COMPETITOR_PROFILES:
            cards[key] = generate_battle_card(key, conn)
        return {
            "battle_cards": cards,
            "total_competitors": len(cards),
            "generated_at": datetime.now().isoformat(),
        }
    finally:
        if close_conn:
            conn.close()


def _find_competitor_signals(conn, profile: dict) -> list[dict]:
    """Find signals mentioning a competitor by name or aliases."""
    all_names = [profile["name"].lower()] + [a.lower() for a in profile.get("aliases", [])]

    conditions = " OR ".join(
        "(LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)"
        for _ in all_names
    )
    params = []
    for name in all_names:
        params.extend([f"%{name}%", f"%{name}%"])

    rows = conn.execute(f"""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.what_summary, sa.quick_win, s.url, s.source_name,
               s.collected_at
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND ({conditions})
        ORDER BY s.collected_at DESC
        LIMIT 20
    """, params).fetchall()

    return [
        {
            "signal_id": r[0],
            "headline": r[1],
            "signal_type": r[2],
            "score": r[3] or 0,
            "summary": r[4],
            "quick_win": r[5],
            "url": r[6],
            "source": r[7],
            "date": r[8],
        }
        for r in rows
    ]


def _analyze_signal_patterns(signals: list[dict]) -> dict:
    """Analyze patterns in competitor signals."""
    if not signals:
        return {"trend": "no-data", "dominant_type": None, "activity_level": "none"}

    from collections import Counter
    types = Counter(s["signal_type"] for s in signals)
    dominant = types.most_common(1)[0] if types else (None, 0)

    # Simple trend: compare recent 7 days vs older
    recent = [s for s in signals if s.get("date", "") >= datetime.now().strftime("%Y-%m-%d")]
    older = [s for s in signals if s.get("date", "") < datetime.now().strftime("%Y-%m-%d")]

    if len(recent) > len(older):
        trend = "increasing"
    elif len(recent) < len(older) * 0.5:
        trend = "decreasing"
    else:
        trend = "stable"

    activity = "high" if len(signals) >= 10 else "medium" if len(signals) >= 5 else "low"

    return {
        "trend": trend,
        "dominant_type": dominant[0],
        "dominant_type_count": dominant[1],
        "type_distribution": dict(types),
        "activity_level": activity,
        "total_signals": len(signals),
    }


def _generate_counter_messages(profile: dict, signals: list[dict]) -> list[dict]:
    """Generate counter-messaging based on competitor activity."""
    messages = []

    # Always include core positioning
    messages.append({
        "scenario": "General Competitive Encounter",
        "message": f"When competing against {profile['name']}: emphasize VPG's {', '.join(profile['vpg_advantages'][:2])}.",
        "priority": "standard",
    })

    # Signal-specific messaging
    for sig in signals[:3]:
        if sig["signal_type"] == "competitive-threat":
            messages.append({
                "scenario": f"Re: {sig['headline'][:60]}",
                "message": f"Counter with VPG's differentiated value: {profile['vpg_advantages'][0]}. Proactive outreach recommended.",
                "priority": "urgent",
                "signal_id": sig["signal_id"],
            })
        elif sig["signal_type"] == "technology-trend":
            messages.append({
                "scenario": f"Tech trend: {sig['headline'][:60]}",
                "message": f"Position VPG's broader technology portfolio and precision advantage vs. {profile['name']}'s narrower focus.",
                "priority": "proactive",
                "signal_id": sig["signal_id"],
            })

    # Weakness-based messaging
    for weakness in profile.get("weaknesses", [])[:2]:
        messages.append({
            "scenario": f"Exploit weakness: {weakness}",
            "message": f"When {profile['name']}'s {weakness.lower()} is a factor, highlight VPG's corresponding strength.",
            "priority": "opportunistic",
        })

    return messages


def list_competitors() -> list[dict]:
    """List all tracked competitors."""
    return [
        {"key": k, "name": v["name"], "segments": v["segments"]}
        for k, v in COMPETITOR_PROFILES.items()
    ]
