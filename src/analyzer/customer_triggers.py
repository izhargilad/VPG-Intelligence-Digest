"""Customer expansion trigger detection for VPG Intelligence Digest.

Monitors signals for known VPG customers announcing:
- Facility expansion / new plant construction
- New product launches
- Hiring surges / new engineering roles
- Acquisitions or mergers
- Capital expenditure increases

When detected, auto-generates upsell/cross-sell briefs with specific
VPG products from relevant BUs.
"""

import logging
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Expansion trigger keywords
EXPANSION_KEYWORDS = [
    "new facility", "plant expansion", "new plant", "factory opening",
    "groundbreaking", "facility expansion", "capacity expansion",
    "new manufacturing", "production expansion",
]

PRODUCT_LAUNCH_KEYWORDS = [
    "new product", "product launch", "launches", "unveils",
    "introduces", "next-generation", "next gen",
]

HIRING_KEYWORDS = [
    "hiring", "new jobs", "job openings", "engineers wanted",
    "expanding team", "workforce expansion", "recruiting",
]

CAPEX_KEYWORDS = [
    "capital expenditure", "capex", "investment", "billion dollar",
    "million dollar", "funding round", "raises",
]

ACQUISITION_KEYWORDS = [
    "acquires", "acquisition", "merger", "merges with",
    "takes over", "buyout", "joint venture",
]

# Known VPG customers and prospects with product mappings
KNOWN_CUSTOMERS = {
    "caterpillar": {
        "name": "Caterpillar",
        "products": ["Load cells", "Onboard weighing", "Force sensors"],
        "bus": ["vpg-force-sensors", "vpg-onboard-weighing", "blh-nobel"],
    },
    "boeing": {
        "name": "Boeing",
        "products": ["Strain gages", "DAQ systems", "Precision resistors"],
        "bus": ["micro-measurements", "pacific-instruments", "vpg-foil-resistors"],
    },
    "lockheed": {
        "name": "Lockheed Martin",
        "products": ["Foil resistors", "DAQ systems", "Strain gages"],
        "bus": ["vpg-foil-resistors", "pacific-instruments", "micro-measurements"],
    },
    "general motors": {
        "name": "General Motors",
        "products": ["Crash test DAQ", "Strain gages", "Force sensors"],
        "bus": ["dts", "micro-measurements", "vpg-force-sensors"],
    },
    "ford": {
        "name": "Ford",
        "products": ["Crash test DAQ", "Strain gages"],
        "bus": ["dts", "micro-measurements"],
    },
    "tesla": {
        "name": "Tesla",
        "products": ["Force sensors", "Strain gages", "DAQ systems"],
        "bus": ["vpg-force-sensors", "micro-measurements", "dts"],
    },
    "john deere": {
        "name": "John Deere",
        "products": ["Onboard weighing", "Load cells", "Force sensors"],
        "bus": ["vpg-onboard-weighing", "vpg-force-sensors", "blh-nobel"],
    },
    "raytheon": {
        "name": "Raytheon",
        "products": ["Foil resistors", "DAQ systems"],
        "bus": ["vpg-foil-resistors", "pacific-instruments"],
    },
    "arcelormittal": {
        "name": "ArcelorMittal",
        "products": ["Rolling mill systems", "Process weighing"],
        "bus": ["kelk", "blh-nobel"],
    },
    "nucor": {
        "name": "Nucor",
        "products": ["Rolling mill systems", "Laser measurement"],
        "bus": ["kelk"],
    },
    "waste management": {
        "name": "Waste Management",
        "products": ["Onboard weighing systems"],
        "bus": ["vpg-onboard-weighing"],
    },
}


def detect_customer_triggers(conn=None) -> dict:
    """Scan scored signals for customer expansion triggers.

    Returns:
        Dict with detected triggers grouped by customer and type.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        triggers = []

        for customer_key, customer in KNOWN_CUSTOMERS.items():
            customer_triggers = _find_customer_signals(conn, customer_key, customer)
            if customer_triggers:
                triggers.append({
                    "customer": customer["name"],
                    "customer_key": customer_key,
                    "triggers": customer_triggers,
                    "recommended_products": customer["products"],
                    "relevant_bus": customer["bus"],
                    "upsell_brief": _generate_upsell_brief(customer, customer_triggers),
                })

        return {
            "triggers": triggers,
            "total_triggers": sum(len(t["triggers"]) for t in triggers),
            "customers_with_triggers": len(triggers),
            "analyzed_at": datetime.now().isoformat(),
        }

    finally:
        if close_conn:
            conn.close()


def _find_customer_signals(conn, customer_key: str, customer: dict) -> list[dict]:
    """Find signals mentioning a customer with expansion-related keywords."""
    name = customer["name"].lower()

    rows = conn.execute("""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.what_summary, s.url, s.collected_at
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
          AND s.collected_at >= datetime('now', '-30 days')
        ORDER BY sa.score_composite DESC
        LIMIT 10
    """, (f"%{name}%", f"%{name}%")).fetchall()

    triggers = []
    for row in rows:
        text = f"{row[1]} {row[4] or ''}".lower()
        trigger_type = _classify_trigger(text)
        if trigger_type:
            triggers.append({
                "signal_id": row[0],
                "headline": row[1],
                "signal_type": row[2],
                "score": row[3],
                "trigger_type": trigger_type,
                "url": row[5],
                "date": row[6],
            })

    return triggers


def _classify_trigger(text: str) -> str | None:
    """Classify the type of expansion trigger from signal text."""
    text = text.lower()

    if any(kw in text for kw in EXPANSION_KEYWORDS):
        return "facility-expansion"
    if any(kw in text for kw in PRODUCT_LAUNCH_KEYWORDS):
        return "product-launch"
    if any(kw in text for kw in HIRING_KEYWORDS):
        return "hiring-surge"
    if any(kw in text for kw in CAPEX_KEYWORDS):
        return "capex-increase"
    if any(kw in text for kw in ACQUISITION_KEYWORDS):
        return "acquisition"

    return None


def _generate_upsell_brief(customer: dict, triggers: list[dict]) -> dict:
    """Generate an upsell/cross-sell brief for a customer."""
    trigger_types = set(t["trigger_type"] for t in triggers)

    actions = []
    if "facility-expansion" in trigger_types:
        actions.append(f"New {customer['name']} facility will need measurement and sensing equipment. Prepare a solution package featuring {', '.join(customer['products'][:2])}.")
    if "product-launch" in trigger_types:
        actions.append(f"{customer['name']} new product may require testing and validation equipment. Position VPG's testing solutions.")
    if "hiring-surge" in trigger_types:
        actions.append(f"{customer['name']} hiring indicates growth. Reach out to new engineering contacts for VPG product evaluations.")
    if "capex-increase" in trigger_types:
        actions.append(f"{customer['name']} capital investment signals budget availability. Prepare ROI-focused proposals for VPG solutions.")
    if "acquisition" in trigger_types:
        actions.append(f"{customer['name']} acquisition/merger may consolidate vendors. Proactively position VPG as preferred supplier across combined operations.")

    if not actions:
        actions.append(f"Monitor {customer['name']} developments and prepare updated account brief.")

    return {
        "customer_name": customer["name"],
        "trigger_count": len(triggers),
        "trigger_types": list(trigger_types),
        "recommended_actions": actions,
        "products_to_propose": customer["products"],
        "priority": "high" if len(triggers) >= 2 else "medium",
    }
