"""Meeting prep briefs for VPG target accounts.

When signals mention strategic target accounts (Caterpillar, Humanetics,
Saronic, etc.), auto-generates a 1-page account intelligence brief
for salesperson preparation.
"""

import logging
from datetime import datetime

from src.config import CONFIG_DIR, get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Key target accounts to monitor (from BRIEF.md + business context)
TARGET_ACCOUNTS = {
    "caterpillar": {
        "name": "Caterpillar Inc.",
        "industry": "Heavy Equipment & Mining",
        "relevant_bus": ["vpg-force-sensors", "vpg-onboard-weighing", "blh-nobel"],
        "relationship": "Strategic target — global fleet & equipment manufacturer",
        "key_products": ["Load cells for equipment weighing", "Onboard weighing systems", "Force sensors for hydraulic monitoring"],
    },
    "humanetics": {
        "name": "Humanetics Innovative Solutions",
        "industry": "Automotive Safety Testing",
        "relevant_bus": ["dts", "vpg-force-sensors", "micro-measurements"],
        "relationship": "Strategic target — crash test dummy & safety systems",
        "key_products": ["Miniature DAQ for crash test", "Strain gages for dummy instrumentation", "Force sensors for impact measurement"],
    },
    "saronic": {
        "name": "Saronic Technologies",
        "industry": "Defense & Autonomous Vessels",
        "relevant_bus": ["vpg-force-sensors", "pacific-instruments", "vpg-foil-resistors"],
        "relationship": "Strategic target — autonomous naval vessels",
        "key_products": ["Precision resistors for navigation", "DAQ for vessel monitoring", "Force sensors for autonomous systems"],
    },
    "figure-ai": {
        "name": "Figure AI",
        "industry": "Humanoid Robotics",
        "relevant_bus": ["vpg-force-sensors", "micro-measurements"],
        "relationship": "Emerging target — humanoid robot manufacturer",
        "key_products": ["Force/torque sensors for robotic joints", "Strain gages for structural monitoring"],
    },
    "boston-dynamics": {
        "name": "Boston Dynamics",
        "industry": "Robotics & Automation",
        "relevant_bus": ["vpg-force-sensors", "micro-measurements", "dts"],
        "relationship": "Strategic target — advanced robotics platforms",
        "key_products": ["Force sensors for robot actuators", "Miniature DAQ for motion capture", "Strain gages for fatigue testing"],
    },
}


def generate_meeting_brief(account_key: str, conn=None) -> dict:
    """Generate a meeting prep brief for a target account.

    Args:
        account_key: Key from TARGET_ACCOUNTS dict (e.g., 'caterpillar').
        conn: DB connection.

    Returns:
        Complete meeting prep brief dict.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        account = TARGET_ACCOUNTS.get(account_key)
        if not account:
            return {"error": f"Unknown target account: {account_key}"}

        bu_config = get_business_units()
        bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

        # Find recent signals mentioning this account
        recent_signals = _find_account_signals(conn, account)

        # Find industry signals relevant to this account
        industry_signals = _find_industry_signals(conn, account)

        # Find competitor activity in this account's space
        competitor_activity = _find_competitor_activity(conn, account)

        # Generate talking points
        talking_points = _generate_account_talking_points(account, recent_signals, bu_names)

        return {
            "account": account,
            "generated_at": datetime.now().isoformat(),
            "recent_signals": recent_signals,
            "industry_context": industry_signals,
            "competitor_activity": competitor_activity,
            "talking_points": talking_points,
            "vpg_solutions": _map_vpg_solutions(account, bu_config),
            "summary": {
                "account_name": account["name"],
                "signals_found": len(recent_signals),
                "industry_signals": len(industry_signals),
                "competitor_mentions": len(competitor_activity),
            },
        }

    finally:
        if close_conn:
            conn.close()


def _find_account_signals(conn, account: dict) -> list[dict]:
    """Find signals that directly mention the account."""
    name = account["name"].lower()
    # Also search for common abbreviations/short names
    search_terms = [name]
    short = name.split()[0].lower()
    if short != name:
        search_terms.append(short)

    conditions = " OR ".join(
        "(LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)"
        for _ in search_terms
    )
    params = []
    for term in search_terms:
        params.extend([f"%{term}%", f"%{term}%"])

    rows = conn.execute(f"""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.what_summary, sa.why_it_matters, sa.quick_win,
               s.url, s.source_name, s.collected_at
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND ({conditions})
        ORDER BY s.collected_at DESC
        LIMIT 10
    """, params).fetchall()

    return [dict(r) for r in rows]


def _find_industry_signals(conn, account: dict) -> list[dict]:
    """Find signals relevant to the account's industry."""
    industry = account["industry"].lower()
    keywords = industry.split(" & ") + industry.split(", ")
    keywords = [k.strip().lower() for k in keywords if k.strip()]

    if not keywords:
        return []

    conditions = " OR ".join(
        "(LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)"
        for _ in keywords
    )
    params = []
    for kw in keywords:
        params.extend([f"%{kw}%", f"%{kw}%"])

    rows = conn.execute(f"""
        SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
               sa.what_summary, s.url, s.source_name, s.collected_at
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND ({conditions})
          AND s.collected_at >= datetime('now', '-30 days')
        ORDER BY sa.score_composite DESC
        LIMIT 10
    """, params).fetchall()

    return [dict(r) for r in rows]


def _find_competitor_activity(conn, account: dict) -> list[dict]:
    """Find competitor signals relevant to this account's space."""
    bus = account.get("relevant_bus", [])
    if not bus:
        return []

    # Get competitors for the relevant BUs
    bu_config = get_business_units()
    competitors = set()
    for bu in bu_config.get("business_units", []):
        if bu["id"] in bus:
            competitors.update(bu.get("key_competitors", []))

    if not competitors:
        return []

    results = []
    for comp in list(competitors)[:10]:
        rows = conn.execute("""
            SELECT sa.headline, sa.signal_type, sa.score_composite,
                   s.url, s.collected_at
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
              AND s.collected_at >= datetime('now', '-30 days')
            ORDER BY s.collected_at DESC
            LIMIT 3
        """, (f"%{comp.lower()}%", f"%{comp.lower()}%")).fetchall()

        if rows:
            results.append({
                "competitor": comp,
                "signals": [dict(r) for r in rows],
            })

    return results


def _generate_account_talking_points(account: dict, signals: list[dict],
                                     bu_names: dict) -> list[dict]:
    """Generate account-specific talking points."""
    points = []

    # Recent signal-based points
    for sig in signals[:3]:
        points.append({
            "category": "Recent Intelligence",
            "point": sig.get("headline", ""),
            "detail": sig.get("what_summary", ""),
            "action": sig.get("quick_win", ""),
        })

    # VPG solution alignment
    for bu_id in account.get("relevant_bus", [])[:3]:
        bu_name = bu_names.get(bu_id, bu_id)
        products = account.get("key_products", [])
        if products:
            points.append({
                "category": "VPG Solution",
                "point": f"{bu_name}: {products[0] if len(products) > 0 else 'Precision solutions'}",
                "detail": ", ".join(products),
                "action": f"Prepare {bu_name} demo/sample for meeting",
            })

    # India advantage (always relevant)
    points.append({
        "category": "Competitive Edge",
        "point": "India production hub — tariff-free, supply chain resilient",
        "detail": "VPG India manufacturing avoids US-China tariff exposure with competitive pricing and reliable delivery.",
        "action": "Mention supply chain resilience in pricing discussions",
    })

    return points


def _map_vpg_solutions(account: dict, bu_config: dict) -> list[dict]:
    """Map VPG solutions to the account's needs."""
    solutions = []
    bus = {bu["id"]: bu for bu in bu_config.get("business_units", [])}

    for i, bu_id in enumerate(account.get("relevant_bus", [])):
        bu = bus.get(bu_id, {})
        product = account.get("key_products", [])[i] if i < len(account.get("key_products", [])) else ""
        solutions.append({
            "bu_id": bu_id,
            "bu_name": bu.get("name", bu_id),
            "product_fit": product,
            "key_products": bu.get("key_products", []),
        })

    return solutions


def list_target_accounts() -> list[dict]:
    """List all configured target accounts."""
    return [
        {"key": k, **v}
        for k, v in TARGET_ACCOUNTS.items()
    ]
