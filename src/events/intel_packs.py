"""Pre-event intelligence packs for VPG Intelligence Digest.

Before major industry events (AISTech, IMTS, Sensors Expo, etc.),
auto-compiles intelligence on:
- Confirmed exhibitors relevant to VPG
- Announced products from competitors and partners
- Potential meeting targets with context
- VPG talking points and competitive positioning

Events are configured in config/events.json and tracked in the DB.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.config import CONFIG_DIR, get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Default events configuration
DEFAULT_EVENTS = {
    "events": [
        {
            "id": "aistech-2026",
            "name": "AISTech 2026",
            "description": "Iron & Steel Technology Conference & Exposition",
            "start_date": "2026-05-04",
            "end_date": "2026-05-07",
            "location": "Nashville, TN",
            "relevant_bus": ["kelk", "blh-nobel"],
            "key_topics": ["steel production", "rolling mill", "laser measurement", "alpha.ti", "Nokra"],
            "competitors_attending": ["HBK", "Kistler", "Mettler Toledo"],
            "vpg_presence": "Exhibitor — launching KELK-Nokra alpha.ti laser thickness measurement",
            "prep_weeks_before": 4,
        },
        {
            "id": "imts-2026",
            "name": "IMTS 2026",
            "description": "International Manufacturing Technology Show",
            "start_date": "2026-09-14",
            "end_date": "2026-09-19",
            "location": "Chicago, IL",
            "relevant_bus": ["vpg-force-sensors", "micro-measurements", "dts"],
            "key_topics": ["manufacturing automation", "quality inspection", "precision measurement"],
            "competitors_attending": ["HBK", "Kistler", "Kyowa"],
            "vpg_presence": "Exhibitor",
            "prep_weeks_before": 4,
        },
        {
            "id": "sensors-converge-2026",
            "name": "Sensors Converge 2026",
            "description": "Leading sensors and electronics conference",
            "start_date": "2026-06-22",
            "end_date": "2026-06-24",
            "location": "San Jose, CA",
            "relevant_bus": ["vpg-force-sensors", "vpg-foil-resistors", "pacific-instruments", "dts"],
            "key_topics": ["sensor technology", "IoT", "data acquisition", "precision measurement"],
            "competitors_attending": ["TT Electronics", "NMB", "Omega"],
            "vpg_presence": "Exhibitor",
            "prep_weeks_before": 3,
        },
        {
            "id": "automechanika-2026",
            "name": "Automechanika Frankfurt 2026",
            "description": "Global automotive aftermarket trade fair",
            "start_date": "2026-09-13",
            "end_date": "2026-09-17",
            "location": "Frankfurt, Germany",
            "relevant_bus": ["dts", "vpg-onboard-weighing"],
            "key_topics": ["automotive testing", "crash test", "vehicle safety", "fleet management"],
            "competitors_attending": ["Kistler", "Kyowa"],
            "vpg_presence": "Visitor",
            "prep_weeks_before": 3,
        },
    ]
}

EVENTS_FILE = CONFIG_DIR / "events.json"


def _load_events() -> dict:
    """Load events configuration, creating default if missing."""
    if not EVENTS_FILE.exists():
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_EVENTS, f, indent=2)
        logger.info("Created default events.json with %d events", len(DEFAULT_EVENTS["events"]))
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_events(data: dict) -> None:
    """Save events configuration."""
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_upcoming_events(days_ahead: int = 60) -> list[dict]:
    """Get events happening within the next N days.

    Returns:
        List of event dicts with added 'days_until' field.
    """
    config = _load_events()
    now = datetime.now().date()
    cutoff = now + timedelta(days=days_ahead)

    upcoming = []
    for event in config.get("events", []):
        try:
            start = datetime.strptime(event["start_date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue

        if now <= start <= cutoff:
            event_copy = dict(event)
            event_copy["days_until"] = (start - now).days
            event_copy["needs_prep"] = (start - now).days <= event.get("prep_weeks_before", 4) * 7
            upcoming.append(event_copy)

    upcoming.sort(key=lambda e: e["days_until"])
    return upcoming


def generate_intel_pack(event_id: str, conn=None) -> dict:
    """Generate a pre-event intelligence pack for a specific event.

    Compiles:
    - Recent signals relevant to the event's topics and BUs
    - Competitor intelligence for known attendees
    - VPG talking points and positioning
    - Suggested meeting targets from signal data

    Args:
        event_id: ID of the event from events.json
        conn: DB connection (creates one if None)

    Returns:
        Intel pack dict with all compiled intelligence.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        config = _load_events()
        event = next((e for e in config.get("events", []) if e["id"] == event_id), None)
        if not event:
            return {"error": f"Event '{event_id}' not found"}

        bu_config = get_business_units()
        bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

        # 1. Relevant signals from the last 30 days
        relevant_signals = _find_relevant_signals(conn, event)

        # 2. Competitor intelligence
        competitor_intel = _compile_competitor_intel(conn, event)

        # 3. VPG talking points
        talking_points = _generate_talking_points(event, relevant_signals, bu_names)

        # 4. Suggested meeting targets
        meeting_targets = _identify_meeting_targets(conn, event, relevant_signals)

        return {
            "event": event,
            "generated_at": datetime.now().isoformat(),
            "relevant_signals": relevant_signals,
            "competitor_intel": competitor_intel,
            "talking_points": talking_points,
            "meeting_targets": meeting_targets,
            "summary": {
                "signals_found": len(relevant_signals),
                "competitors_tracked": len(competitor_intel),
                "meeting_targets": len(meeting_targets),
                "relevant_bus": [bu_names.get(b, b) for b in event.get("relevant_bus", [])],
            },
        }

    finally:
        if close_conn:
            conn.close()


def _find_relevant_signals(conn, event: dict) -> list[dict]:
    """Find signals relevant to the event's topics and BUs."""
    # Build keyword search conditions
    topics = event.get("key_topics", [])
    bus = event.get("relevant_bus", [])

    if not topics and not bus:
        return []

    # Search by BU association
    bu_signals = []
    if bus:
        placeholders = ",".join("?" * len(bus))
        rows = conn.execute(f"""
            SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
                   sa.what_summary, sa.quick_win, s.url, s.source_name,
                   GROUP_CONCAT(DISTINCT sb.bu_id) as bus
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_bus sb ON s.id = sb.signal_id
            WHERE s.status IN ('scored', 'published')
              AND sb.bu_id IN ({placeholders})
              AND s.collected_at >= datetime('now', '-30 days')
            GROUP BY s.id
            ORDER BY sa.score_composite DESC
            LIMIT 20
        """, bus).fetchall()
        bu_signals = [dict(r) for r in rows]

    # Search by topic keywords in title/summary
    topic_signals = []
    for topic in topics:
        rows = conn.execute("""
            SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
                   sa.what_summary, sa.quick_win, s.url, s.source_name
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND s.collected_at >= datetime('now', '-30 days')
              AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
            ORDER BY sa.score_composite DESC
            LIMIT 5
        """, (f"%{topic.lower()}%", f"%{topic.lower()}%")).fetchall()
        topic_signals.extend(dict(r) for r in rows)

    # Merge and deduplicate
    seen = set()
    merged = []
    for sig in bu_signals + topic_signals:
        if sig["id"] not in seen:
            seen.add(sig["id"])
            merged.append(sig)

    merged.sort(key=lambda s: s.get("score_composite", 0) or 0, reverse=True)
    return merged[:15]


def _compile_competitor_intel(conn, event: dict) -> list[dict]:
    """Compile intelligence on competitors attending the event."""
    competitors = event.get("competitors_attending", [])
    if not competitors:
        return []

    intel = []
    for comp in competitors:
        rows = conn.execute("""
            SELECT sa.headline, sa.signal_type, sa.score_composite,
                   sa.what_summary, s.url, s.collected_at
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
            ORDER BY s.collected_at DESC
            LIMIT 5
        """, (f"%{comp.lower()}%", f"%{comp.lower()}%")).fetchall()

        signals = [dict(r) for r in rows]
        intel.append({
            "competitor": comp,
            "recent_signals": signals,
            "signal_count": len(signals),
            "avg_score": round(
                sum(s.get("score_composite", 0) or 0 for s in signals) / max(len(signals), 1), 1
            ),
        })

    return intel


def _generate_talking_points(event: dict, signals: list[dict], bu_names: dict) -> list[dict]:
    """Generate VPG talking points for the event."""
    points = []

    # VPG presence talking point
    if event.get("vpg_presence"):
        points.append({
            "category": "VPG Presence",
            "point": event["vpg_presence"],
            "priority": "high",
        })

    # BU-specific points from high-scoring signals
    bu_signals = defaultdict(list)
    for sig in signals:
        for bu_id in (sig.get("bus", "") or "").split(","):
            if bu_id.strip():
                bu_signals[bu_id.strip()].append(sig)

    for bu_id in event.get("relevant_bus", []):
        bu_name = bu_names.get(bu_id, bu_id)
        sigs = bu_signals.get(bu_id, [])
        if sigs:
            top = sigs[0]
            points.append({
                "category": bu_name,
                "point": f"Key signal: {top.get('headline', 'N/A')} (score {top.get('score_composite', 0):.1f})",
                "action": top.get("quick_win", ""),
                "priority": "high" if (top.get("score_composite", 0) or 0) >= 7 else "medium",
            })
        else:
            points.append({
                "category": bu_name,
                "point": "No recent signals — use event for market intelligence gathering.",
                "priority": "low",
            })

    # India production advantage point (always relevant at trade shows)
    points.append({
        "category": "India Advantage",
        "point": "VPG's India production hub offers supply chain resilience vs. China-dependent competitors. Highlight tariff advantages and delivery reliability.",
        "priority": "medium",
    })

    return points


def _identify_meeting_targets(conn, event: dict, signals: list[dict]) -> list[dict]:
    """Identify potential meeting targets from signal data."""
    targets = []

    # Extract company names mentioned in high-scoring signals
    # that relate to the event's topics
    for sig in signals[:10]:
        if (sig.get("score_composite", 0) or 0) >= 6.0:
            headline = sig.get("headline", "")
            signal_type = sig.get("signal_type", "")

            if signal_type in ("revenue-opportunity", "customer-intelligence", "partnership-signal"):
                targets.append({
                    "context": headline,
                    "signal_type": signal_type,
                    "score": sig.get("score_composite", 0),
                    "action": sig.get("quick_win", ""),
                    "source_url": sig.get("url", ""),
                })

    return targets[:10]


# ── CRUD for events ──────────────────────────────────────────────────

def list_events() -> list[dict]:
    """List all configured events."""
    config = _load_events()
    return config.get("events", [])


def add_event(event: dict) -> dict:
    """Add a new event to the configuration."""
    config = _load_events()
    config.setdefault("events", []).append(event)
    _save_events(config)
    return event


def update_event(event_id: str, updates: dict) -> dict | None:
    """Update an existing event."""
    config = _load_events()
    for i, event in enumerate(config.get("events", [])):
        if event["id"] == event_id:
            config["events"][i].update(updates)
            _save_events(config)
            return config["events"][i]
    return None


def delete_event(event_id: str) -> bool:
    """Delete an event from the configuration."""
    config = _load_events()
    events = config.get("events", [])
    config["events"] = [e for e in events if e["id"] != event_id]
    if len(config["events"]) < len(events):
        _save_events(config)
        return True
    return False
