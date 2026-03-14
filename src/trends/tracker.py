"""Trend tracking and pattern detection for VPG Intelligence Digest.

Analyzes signal patterns over time to identify:
- Rising/declining trends by BU and signal type
- Competitor activity spikes
- Industry momentum shifts
- Keyword frequency changes

Updated after each pipeline run to build a time-series view of intelligence patterns.
"""

import logging
from collections import defaultdict
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection, init_db

logger = logging.getLogger(__name__)


def _get_current_week() -> tuple[int, int]:
    """Get current ISO week number and year."""
    now = datetime.now()
    iso = now.isocalendar()
    return iso[1], iso[0]


def update_trends(conn=None) -> dict:
    """Analyze scored signals and update trend data.

    Should be called after each pipeline scoring stage.

    Returns:
        Summary dict with trend counts and notable changes.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()
        init_db()

    week_num, year = _get_current_week()

    try:
        # Get all scored signals from the current week
        signals = conn.execute("""
            SELECT s.id, s.title, s.summary, sa.signal_type,
                   sa.score_composite, sa.headline, s.published_at
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
            ORDER BY sa.score_composite DESC
        """).fetchall()

        if not signals:
            logger.info("No scored signals for trend analysis")
            return {"trends_updated": 0, "notable": []}

        # Get BU associations
        bu_assoc = defaultdict(list)
        for row in conn.execute("SELECT signal_id, bu_id FROM signal_bus"):
            bu_assoc[row[0]].append(row[1])

        # Get industry associations
        ind_assoc = defaultdict(list)
        for row in conn.execute("SELECT signal_id, industry_id FROM signal_industries"):
            ind_assoc[row[0]].append(row[1])

        # Get industry names
        ind_names = {}
        for row in conn.execute("SELECT id, name FROM industries"):
            ind_names[row[0]] = row[1]

        # Build trend aggregations
        aggregations = defaultdict(lambda: {"count": 0, "scores": [], "signal_ids": []})

        bu_config = get_business_units()
        bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

        for sig in signals:
            sig_id = sig[0]
            sig_type = sig[3]
            score = sig[4] or 0

            # Trend by BU + signal type
            for bu_id in bu_assoc.get(sig_id, []):
                key = f"{bu_id}:{sig_type}"
                label = f"{bu_names.get(bu_id, bu_id)} - {sig_type.replace('-', ' ').title()}"
                agg = aggregations[key]
                agg["trend_type"] = "bu_signal_type"
                agg["label"] = label
                agg["count"] += 1
                agg["scores"].append(score)
                agg["signal_ids"].append(sig_id)

            # Trend by signal type alone
            type_key = f"type:{sig_type}"
            type_agg = aggregations[type_key]
            type_agg["trend_type"] = "signal_type"
            type_agg["label"] = sig_type.replace("-", " ").title()
            type_agg["count"] += 1
            type_agg["scores"].append(score)
            type_agg["signal_ids"].append(sig_id)

            # Trend by BU alone
            for bu_id in bu_assoc.get(sig_id, []):
                bu_key = f"bu:{bu_id}"
                bu_agg = aggregations[bu_key]
                bu_agg["trend_type"] = "business_unit"
                bu_agg["label"] = bu_names.get(bu_id, bu_id)
                bu_agg["count"] += 1
                bu_agg["scores"].append(score)
                bu_agg["signal_ids"].append(sig_id)

            # Competitor keyword detection
            text = f"{sig[1]} {sig[2]}".lower()
            competitors = [
                "kistler", "hbk", "zemic", "rice lake", "tt electronics",
                "kyowa", "flintec", "omega", "novanta", "figure ai",
                "boston dynamics", "sunrise instruments",
            ]
            for comp in competitors:
                if comp in text:
                    comp_key = f"competitor:{comp}"
                    comp_agg = aggregations[comp_key]
                    comp_agg["trend_type"] = "competitor"
                    comp_agg["label"] = comp.title()
                    comp_agg["count"] += 1
                    comp_agg["scores"].append(score)
                    comp_agg["signal_ids"].append(sig_id)

            # Trend by industry
            for ind_id in ind_assoc.get(sig_id, []):
                ind_key = f"industry:{ind_id}"
                ind_agg = aggregations[ind_key]
                ind_agg["trend_type"] = "industry"
                ind_agg["label"] = ind_names.get(ind_id, ind_id)
                ind_agg["count"] += 1
                ind_agg["scores"].append(score)
                ind_agg["signal_ids"].append(sig_id)

        # Upsert trends and create snapshots
        trends_updated = 0
        notable = []

        for trend_key, agg in aggregations.items():
            avg_score = sum(agg["scores"]) / len(agg["scores"]) if agg["scores"] else 0
            max_score = max(agg["scores"]) if agg["scores"] else 0
            count = agg["count"]
            top_signal_id = agg["signal_ids"][0] if agg["signal_ids"] else None

            # Check if trend exists
            existing = conn.execute(
                "SELECT id, occurrence_count, avg_score FROM trends WHERE trend_key = ?",
                (trend_key,),
            ).fetchone()

            today = datetime.now().strftime("%Y-%m-%d")

            if existing:
                trend_id = existing[0]
                old_total_count = existing[1]
                old_avg = existing[2] or 0

                # Get the PREVIOUS week's snapshot count for week-over-week comparison
                # (not the accumulated total, which always grows)
                prev_snapshot = conn.execute(
                    """SELECT signal_count FROM trend_snapshots
                       WHERE trend_id = ? AND NOT (week_number = ? AND year = ?)
                       ORDER BY year DESC, week_number DESC LIMIT 1""",
                    (trend_id, week_num, year),
                ).fetchone()
                prev_count = prev_snapshot[0] if prev_snapshot else count  # default to same = stable

                # Calculate momentum based on week-over-week comparison
                change = ((count - prev_count) / max(prev_count, 1)) * 100
                if count > prev_count * 1.5:
                    momentum = "spike"
                elif count > prev_count:
                    momentum = "rising"
                elif count == prev_count:
                    momentum = "stable"
                elif count < prev_count * 0.5:
                    momentum = "declining"
                else:
                    momentum = "stable"  # small decrease = still stable

                conn.execute("""
                    UPDATE trends SET
                        last_seen = ?, occurrence_count = ?,
                        week_over_week_change = ?, avg_score = ?,
                        max_score = MAX(max_score, ?), momentum = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                """, (today, count, round(change, 1), round(avg_score, 2),
                      max_score, momentum, trend_id))

                if momentum in ("spike", "rising"):
                    notable.append({
                        "trend": agg["label"],
                        "momentum": momentum,
                        "count": count,
                        "change_pct": round(change, 1),
                    })
            else:
                # New trend
                cursor = conn.execute("""
                    INSERT INTO trends (trend_key, trend_type, label,
                        first_seen, last_seen, occurrence_count,
                        avg_score, max_score, momentum)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
                """, (trend_key, agg["trend_type"], agg["label"],
                      today, today, count, round(avg_score, 2), max_score))
                trend_id = cursor.lastrowid

                notable.append({
                    "trend": agg["label"],
                    "momentum": "new",
                    "count": count,
                    "change_pct": 0,
                })

            # Upsert weekly snapshot
            conn.execute("""
                INSERT OR REPLACE INTO trend_snapshots
                    (trend_id, week_number, year, signal_count, avg_score, top_signal_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (trend_id, week_num, year, count, round(avg_score, 2), top_signal_id))

            trends_updated += 1

        conn.commit()
        logger.info("Updated %d trends, %d notable changes", trends_updated, len(notable))

        return {
            "trends_updated": trends_updated,
            "notable": notable,
            "week": week_num,
            "year": year,
        }

    finally:
        if close_conn:
            conn.close()


def get_trend_summary(conn=None, limit: int = 20,
                      start_date: str | None = None,
                      end_date: str | None = None) -> dict:
    """Get a summary of current trends for display.

    Dates filter on signal published_at (the actual publication date of
    the underlying signals), not the trend's internal last_seen timestamp.

    Args:
        limit: Max trends to return.
        start_date: Optional YYYY-MM-DD start filter on signal published dates.
        end_date: Optional YYYY-MM-DD end filter on signal published dates.

    Returns:
        Dict with rising, declining, new, and spike trends.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        # When date filters are provided, re-aggregate from actual signal data
        # to ensure we're filtering by published_at (not collected_at)
        if start_date or end_date:
            return _get_trends_by_published_date(conn, limit, start_date, end_date)

        query = """
            SELECT trend_key, trend_type, label, occurrence_count,
                   week_over_week_change, avg_score, max_score, momentum,
                   first_seen, last_seen
            FROM trends
            ORDER BY
                CASE momentum
                    WHEN 'spike' THEN 1
                    WHEN 'rising' THEN 2
                    WHEN 'new' THEN 3
                    WHEN 'stable' THEN 4
                    WHEN 'declining' THEN 5
                END,
                occurrence_count DESC
            LIMIT ?
        """
        rows = conn.execute(query, [limit]).fetchall()

        trends = []
        for row in rows:
            trends.append({
                "key": row[0],
                "type": row[1],
                "label": row[2],
                "count": row[3],
                "change_pct": row[4],
                "avg_score": row[5],
                "max_score": row[6],
                "momentum": row[7],
                "first_seen": row[8],
                "last_seen": row[9],
            })

        return {
            "trends": trends,
            "rising": [t for t in trends if t["momentum"] in ("rising", "spike")],
            "new": [t for t in trends if t["momentum"] == "new"],
            "declining": [t for t in trends if t["momentum"] == "declining"],
        }

    finally:
        if close_conn:
            conn.close()


def _get_trends_by_published_date(conn, limit: int,
                                   start_date: str | None,
                                   end_date: str | None) -> dict:
    """Re-aggregate trend data filtered by signal published_at dates."""
    date_clause = ""
    params: list = []
    if start_date:
        date_clause += " AND COALESCE(s.published_at, s.collected_at) >= ?"
        params.append(start_date)
    if end_date:
        date_clause += " AND COALESCE(s.published_at, s.collected_at) <= ?"
        params.append(end_date + " 23:59:59")

    # Get trends that have signals in the date range via snapshots
    # We join through trend_snapshots -> trends to get matching trend IDs,
    # but actually count signals directly for accuracy
    query = f"""
        SELECT t.trend_key, t.trend_type, t.label,
               COUNT(DISTINCT s.id) as signal_count,
               t.week_over_week_change, AVG(sa.score_composite) as avg_score,
               MAX(sa.score_composite) as max_score, t.momentum,
               t.first_seen, t.last_seen
        FROM trends t
        JOIN trend_snapshots ts ON t.id = ts.trend_id
        JOIN signals s ON ts.top_signal_id = s.id
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          {date_clause}
        GROUP BY t.trend_key
        ORDER BY
            CASE t.momentum
                WHEN 'spike' THEN 1
                WHEN 'rising' THEN 2
                WHEN 'new' THEN 3
                WHEN 'stable' THEN 4
                WHEN 'declining' THEN 5
            END,
            signal_count DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()

    trends = []
    for row in rows:
        trends.append({
            "key": row[0],
            "type": row[1],
            "label": row[2],
            "count": row[3],
            "change_pct": row[4],
            "avg_score": row[5],
            "max_score": row[6],
            "momentum": row[7],
            "first_seen": row[8],
            "last_seen": row[9],
        })

    return {
        "trends": trends,
        "rising": [t for t in trends if t["momentum"] in ("rising", "spike")],
        "new": [t for t in trends if t["momentum"] == "new"],
        "declining": [t for t in trends if t["momentum"] == "declining"],
    }


def get_trend_history(trend_key: str, weeks: int = 12, conn=None) -> list[dict]:
    """Get week-by-week history for a specific trend.

    Returns:
        List of weekly snapshots for charting.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT ts.week_number, ts.year, ts.signal_count, ts.avg_score
            FROM trend_snapshots ts
            JOIN trends t ON ts.trend_id = t.id
            WHERE t.trend_key = ?
            ORDER BY ts.year DESC, ts.week_number DESC
            LIMIT ?
        """, (trend_key, weeks)).fetchall()

        return [
            {"week": r[0], "year": r[1], "count": r[2], "avg_score": r[3]}
            for r in reversed(rows)
        ]

    finally:
        if close_conn:
            conn.close()
