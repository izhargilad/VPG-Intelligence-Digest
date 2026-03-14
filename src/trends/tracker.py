"""Trend tracking and pattern detection for VPG Intelligence Digest.

Analyzes signal patterns over time to identify:
- Rising/declining trends by BU and signal type
- Competitor activity spikes
- Industry momentum shifts
- Keyword frequency changes
- AI-generated "What's Moving" trend alerts (V2.4)

Updated after each pipeline run to build a time-series view of intelligence patterns.
"""

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from src.config import get_business_units
from src.db import get_connection, init_db

logger = logging.getLogger(__name__)

# Competitors monitored for trend detection
COMPETITORS = [
    "kistler", "hbk", "zemic", "rice lake", "tt electronics",
    "kyowa", "flintec", "omega", "novanta", "figure ai",
    "boston dynamics", "sunrise instruments",
]


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
            for comp in COMPETITORS:
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
                prev_snapshot = conn.execute(
                    """SELECT signal_count FROM trend_snapshots
                       WHERE trend_id = ? AND NOT (week_number = ? AND year = ?)
                       ORDER BY year DESC, week_number DESC LIMIT 1""",
                    (trend_id, week_num, year),
                ).fetchone()
                prev_count = prev_snapshot[0] if prev_snapshot else count

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
                    momentum = "stable"

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


# ═══════════════════════════════════════════════════════════════════
# V2.4: Trend Alerts — AI-generated "What's Moving" cards
# ═══════════════════════════════════════════════════════════════════

def generate_trend_alerts(conn=None, bu_code: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None) -> list[dict]:
    """Generate trend alert cards from signal data using heuristic analysis.

    Identifies the top 3-5 named trends based on signal clustering,
    volume changes, and score patterns. Each alert includes companies,
    evidence, and suggested actions.

    Args:
        conn: Optional DB connection.
        bu_code: Optional BU filter.
        start_date: Period start (YYYY-MM-DD).
        end_date: Period end (YYYY-MM-DD).

    Returns:
        List of trend alert dicts.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        # Determine date range
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(weeks=4)).strftime("%Y-%m-%d")

        # Prior period of equal length for comparison
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        period_days = (end_dt - start_dt).days
        prior_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
        prior_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        # Build query for current period signals with industry grouping
        bu_clause = ""
        params_current = [start_date, end_date + " 23:59:59"]
        params_prior = [prior_start, prior_end + " 23:59:59"]

        if bu_code:
            bu_clause = " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
            params_current.append(bu_code)
            params_prior.append(bu_code)

        # Get current period signals grouped by industry
        current_sql = f"""
            SELECT si.industry_id, i.name as industry_name,
                   COUNT(DISTINCT s.id) as signal_count,
                   AVG(sa.score_composite) as avg_score,
                   MAX(sa.score_composite) as max_score,
                   GROUP_CONCAT(sa.headline, '||') as headlines,
                   GROUP_CONCAT(s.id) as signal_ids
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_industries si ON s.id = si.signal_id
            JOIN industries i ON si.industry_id = i.id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
              AND COALESCE(s.published_at, s.collected_at) >= ?
              AND COALESCE(s.published_at, s.collected_at) <= ?
              {bu_clause}
            GROUP BY si.industry_id
            HAVING signal_count >= 2
            ORDER BY signal_count DESC
        """

        current_rows = conn.execute(current_sql, params_current).fetchall()

        # Get prior period for comparison
        prior_sql = f"""
            SELECT si.industry_id, COUNT(DISTINCT s.id) as signal_count
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_industries si ON s.id = si.signal_id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
              AND COALESCE(s.published_at, s.collected_at) >= ?
              AND COALESCE(s.published_at, s.collected_at) <= ?
              {bu_clause}
            GROUP BY si.industry_id
        """
        prior_rows = conn.execute(prior_sql, params_prior).fetchall()
        prior_counts = {r[0]: r[1] for r in prior_rows}

        # Extract company names from signal texts
        def _extract_companies(signal_ids_str):
            if not signal_ids_str:
                return []
            sig_ids = [int(x) for x in signal_ids_str.split(",")]
            companies = set()
            known = COMPETITORS + [
                "figure ai", "agility robotics", "caterpillar",
                "humanetics", "saronic", "fanuc", "abb",
            ]
            for sid in sig_ids:
                row = conn.execute(
                    "SELECT title, summary FROM signals WHERE id = ?", (sid,)
                ).fetchone()
                if row:
                    text = f"{row[0]} {row[1] or ''}".lower()
                    for comp in known:
                        if comp in text:
                            companies.add(comp.title())
            return sorted(companies)[:8]

        # Build trend alerts
        alerts = []
        period_weeks = max(1, period_days // 7)

        for row in current_rows[:5]:
            ind_id = row[0]
            ind_name = row[1]
            count = row[2]
            avg_score = row[3] or 0
            max_score = row[4] or 0
            headlines = (row[5] or "").split("||")
            signal_ids_str = row[6]

            prior_count = prior_counts.get(ind_id, 0)

            # Calculate change
            if prior_count > 0:
                change_pct = round(((count - prior_count) / prior_count) * 100, 1)
            elif count > 0:
                change_pct = 100.0
            else:
                change_pct = 0

            # Determine trend type
            if prior_count == 0 and count > 0:
                trend_type = "new"
            elif change_pct >= 30:
                trend_type = "rising"
            elif change_pct <= -30:
                trend_type = "declining"
            else:
                trend_type = "persistent"

            companies = _extract_companies(signal_ids_str)
            top_headline = headlines[0] if headlines else ""

            # Get top signal ID
            top_signal = conn.execute(f"""
                SELECT s.id FROM signals s
                JOIN signal_analysis sa ON s.id = sa.signal_id
                JOIN signal_industries si ON s.id = si.signal_id
                WHERE si.industry_id = ?
                  AND s.status IN ('scored', 'published')
                  AND COALESCE(s.published_at, s.collected_at) >= ?
                  AND COALESCE(s.published_at, s.collected_at) <= ?
                ORDER BY sa.score_composite DESC LIMIT 1
            """, (ind_id, start_date, end_date + " 23:59:59")).fetchone()
            top_signal_id = top_signal[0] if top_signal else None

            # Get BU code
            bu = None
            if bu_code:
                bu = bu_code
            elif signal_ids_str:
                first_sig_id = int(signal_ids_str.split(",")[0])
                bu_row = conn.execute(
                    "SELECT bu_id FROM signal_bus WHERE signal_id = ? LIMIT 1",
                    (first_sig_id,)
                ).fetchone()
                if bu_row:
                    bu = bu_row[0]

            # Suggested action based on trend type
            if trend_type == "rising":
                action = f"Create targeted content for {ind_name}. Prioritize outreach to top accounts."
            elif trend_type == "new":
                action = f"Investigate {ind_name} signals. Assess strategic fit and competitive landscape."
            elif trend_type == "declining":
                action = f"Monitor {ind_name} for further decline. Prepare defensive positioning if needed."
            else:
                action = f"Continue monitoring {ind_name}. Review persistent signals for emerging patterns."

            # Build named trend
            trend_name = f"{ind_name}"
            if companies:
                trend_name = f"{ind_name} ({', '.join(companies[:2])})"

            signal_ids_list = [int(x) for x in signal_ids_str.split(",")] if signal_ids_str else []

            alert_id = str(uuid.uuid4())[:8]
            alert = {
                "id": alert_id,
                "bu_code": bu,
                "industry": ind_id,
                "industry_name": ind_name,
                "trend_name": trend_name,
                "trend_type": trend_type,
                "change_percent": change_pct,
                "signal_count": count,
                "period_weeks": period_weeks,
                "companies": companies,
                "top_signal_id": top_signal_id,
                "top_signal_headline": top_headline,
                "description": f"{count} signals over {period_weeks} weeks from {ind_name}",
                "suggested_action": action,
                "supporting_signal_ids": signal_ids_list[:20],
            }
            alerts.append(alert)

        # Persist alerts to DB
        for alert in alerts:
            conn.execute("""
                INSERT OR REPLACE INTO trend_alerts
                    (id, bu_code, industry, trend_name, trend_type, change_percent,
                     signal_count, period_weeks, companies, top_signal_id,
                     top_signal_headline, description, suggested_action,
                     supporting_signal_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert["id"], alert["bu_code"], alert["industry"],
                alert["trend_name"], alert["trend_type"], alert["change_percent"],
                alert["signal_count"], alert["period_weeks"],
                json.dumps(alert["companies"]),
                alert["top_signal_id"], alert["top_signal_headline"],
                alert["description"], alert["suggested_action"],
                json.dumps(alert["supporting_signal_ids"]),
            ))
        conn.commit()

        logger.info("Generated %d trend alerts", len(alerts))
        return alerts

    finally:
        if close_conn:
            conn.close()


def get_trend_alerts(conn=None, bu_code: str | None = None,
                     industry: str | None = None,
                     limit: int = 5) -> list[dict]:
    """Retrieve stored trend alerts.

    Args:
        conn: Optional DB connection.
        bu_code: Optional BU filter.
        industry: Optional industry filter.
        limit: Max alerts to return.

    Returns:
        List of trend alert dicts.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        query = "SELECT * FROM trend_alerts WHERE 1=1"
        params: list = []
        if bu_code:
            query += " AND bu_code = ?"
            params.append(bu_code)
        if industry:
            query += " AND industry = ?"
            params.append(industry)
        query += " ORDER BY created_at DESC, signal_count DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        alerts = []
        for row in rows:
            alert = dict(row)
            # Parse JSON fields
            for field in ("companies", "supporting_signal_ids"):
                if alert.get(field) and isinstance(alert[field], str):
                    try:
                        alert[field] = json.loads(alert[field])
                    except (json.JSONDecodeError, TypeError):
                        alert[field] = []
            alerts.append(alert)
        return alerts
    finally:
        if close_conn:
            conn.close()


# ═══════════════════════════════════════════════════════════════════
# V2.4: Industry Momentum data
# ═══════════════════════════════════════════════════════════════════

def get_industry_momentum(conn=None, bu_code: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None) -> list[dict]:
    """Get industry momentum cards with sparkline data, sentiment, and competitor info.

    Returns one card per industry with signal volume, sentiment, and 8-week sparkline.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(weeks=12)).strftime("%Y-%m-%d")

        bu_clause = ""
        params = [start_date, end_date + " 23:59:59"]
        if bu_code:
            bu_clause = " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
            params.append(bu_code)

        # Main query: per-industry stats
        rows = conn.execute(f"""
            SELECT si.industry_id, i.name,
                   COUNT(DISTINCT s.id) as signal_count,
                   AVG(sa.score_composite) as avg_score,
                   SUM(CASE WHEN sa.signal_type = 'revenue-opportunity' THEN 1 ELSE 0 END) as opportunities,
                   SUM(CASE WHEN sa.signal_type = 'competitive-threat' THEN 1 ELSE 0 END) as threats
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_industries si ON s.id = si.signal_id
            JOIN industries i ON si.industry_id = i.id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
              AND COALESCE(s.published_at, s.collected_at) >= ?
              AND COALESCE(s.published_at, s.collected_at) <= ?
              {bu_clause}
            GROUP BY si.industry_id
            ORDER BY signal_count DESC
        """, params).fetchall()

        # Prior period for change calculation
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        period_days = (end_dt - start_dt).days
        prior_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
        prior_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        prior_params = [prior_start, prior_end + " 23:59:59"]
        if bu_code:
            prior_params.append(bu_code)

        prior_rows = conn.execute(f"""
            SELECT si.industry_id, COUNT(DISTINCT s.id) as cnt, AVG(sa.score_composite) as avg
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_industries si ON s.id = si.signal_id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
              AND COALESCE(s.published_at, s.collected_at) >= ?
              AND COALESCE(s.published_at, s.collected_at) <= ?
              {bu_clause}
            GROUP BY si.industry_id
        """, prior_params).fetchall()
        prior_map = {r[0]: {"count": r[1], "avg_score": r[2]} for r in prior_rows}

        # Sparkline: weekly signal counts per industry (8 weeks)
        sparkline_params = [
            (datetime.now() - timedelta(weeks=8)).strftime("%Y-%m-%d"),
            end_date + " 23:59:59",
        ]
        if bu_code:
            sparkline_params.append(bu_code)

        sparkline_rows = conn.execute(f"""
            SELECT si.industry_id,
                   CAST(strftime('%W', COALESCE(s.published_at, s.collected_at)) AS INTEGER) as week_num,
                   COUNT(DISTINCT s.id) as cnt
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_industries si ON s.id = si.signal_id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
              AND COALESCE(s.published_at, s.collected_at) >= ?
              AND COALESCE(s.published_at, s.collected_at) <= ?
              {bu_clause}
            GROUP BY si.industry_id, week_num
            ORDER BY week_num
        """, sparkline_params).fetchall()

        sparkline_map = defaultdict(list)
        for sr in sparkline_rows:
            sparkline_map[sr[0]].append({"week": sr[1], "count": sr[2]})

        # Top competitor per industry
        comp_params = [start_date, end_date + " 23:59:59"]
        if bu_code:
            comp_params.append(bu_code)

        # Detect top competitor per industry from signal text
        industries_list = []
        for row in rows:
            ind_id = row[0]
            ind_name = row[1]
            count = row[2]
            avg_score = row[3] or 0
            opps = row[4]
            threats = row[5]

            prior = prior_map.get(ind_id, {})
            prior_count = prior.get("count", 0)
            prior_avg = prior.get("avg_score", 0)

            if prior_count > 0:
                change_pct = round(((count - prior_count) / prior_count) * 100, 1)
            else:
                change_pct = 100.0 if count > 0 else 0

            score_change = round((avg_score - (prior_avg or 0)), 1) if prior_avg else 0

            total = opps + threats
            if total > 0:
                sentiment_score = (opps - threats) / total
                if sentiment_score > 0.2:
                    sentiment = "positive"
                elif sentiment_score < -0.2:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"
            else:
                sentiment = "neutral"

            # Get top competitor for this industry
            top_comp = _get_top_competitor_for_industry(conn, ind_id, start_date, end_date, bu_code)

            industries_list.append({
                "id": ind_id,
                "name": ind_name,
                "signal_count": count,
                "avg_score": round(avg_score, 1),
                "score_change": score_change,
                "opportunities": opps,
                "threats": threats,
                "sentiment": sentiment,
                "change_percent": change_pct,
                "top_competitor": top_comp,
                "sparkline": sparkline_map.get(ind_id, []),
            })

        return industries_list

    finally:
        if close_conn:
            conn.close()


def _get_top_competitor_for_industry(conn, industry_id, start_date, end_date, bu_code=None):
    """Find the most-mentioned competitor in signals for this industry."""
    bu_clause = ""
    params = [industry_id, start_date, end_date + " 23:59:59"]
    if bu_code:
        bu_clause = " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
        params.append(bu_code)

    sigs = conn.execute(f"""
        SELECT s.title, s.summary FROM signals s
        JOIN signal_industries si ON s.id = si.signal_id
        WHERE si.industry_id = ?
          AND s.status IN ('scored', 'published')
          AND COALESCE(s.published_at, s.collected_at) >= ?
          AND COALESCE(s.published_at, s.collected_at) <= ?
          {bu_clause}
    """, params).fetchall()

    comp_counts = defaultdict(int)
    for sig in sigs:
        text = f"{sig[0]} {sig[1] or ''}".lower()
        for comp in COMPETITORS:
            if comp in text:
                comp_counts[comp] += 1

    if comp_counts:
        top = max(comp_counts, key=comp_counts.get)
        return top.title()
    return None


# ═══════════════════════════════════════════════════════════════════
# V2.4: Signal Volume Over Time (multi-line chart data)
# ═══════════════════════════════════════════════════════════════════

def get_signal_volume_over_time(conn=None, bu_code: str | None = None,
                                weeks: int = 12) -> dict:
    """Get weekly signal volume data for multi-line chart.

    When a BU is selected, returns one line per industry.
    When no BU selected (All BUs), returns one line per BU.

    Returns:
        Dict with 'weeks' (labels), 'series' (list of {id, name, data}).
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        if bu_code:
            # One line per industry for selected BU
            rows = conn.execute("""
                SELECT si.industry_id, i.name,
                       CAST(strftime('%W', COALESCE(s.published_at, s.collected_at)) AS INTEGER) as week_num,
                       strftime('%Y', COALESCE(s.published_at, s.collected_at)) as yr,
                       COUNT(DISTINCT s.id) as cnt,
                       AVG(sa.score_composite) as avg_score
                FROM signals s
                JOIN signal_analysis sa ON s.id = sa.signal_id
                JOIN signal_industries si ON s.id = si.signal_id
                JOIN industries i ON si.industry_id = i.id
                JOIN signal_bus sb ON s.id = sb.signal_id
                WHERE s.status IN ('scored', 'published')
                  AND COALESCE(s.dismissed, 0) = 0
                  AND sb.bu_id = ?
                  AND COALESCE(s.published_at, s.collected_at) >= ?
                GROUP BY si.industry_id, week_num, yr
                ORDER BY yr, week_num
            """, (bu_code, start_date)).fetchall()

            # Build series
            series_data = defaultdict(lambda: {"name": "", "data": {}})
            all_weeks = set()
            for row in rows:
                ind_id = row[0]
                ind_name = row[1]
                week_label = f"W{row[2]}"
                all_weeks.add((row[3], row[2], week_label))
                series_data[ind_id]["name"] = ind_name
                series_data[ind_id]["data"][week_label] = {
                    "count": row[4],
                    "avg_score": round(row[5] or 0, 1),
                }
        else:
            # One line per BU
            bu_config = get_business_units()
            bu_names = {bu["id"]: bu.get("short_name", bu["name"])
                        for bu in bu_config.get("business_units", [])}

            rows = conn.execute("""
                SELECT sb.bu_id,
                       CAST(strftime('%W', COALESCE(s.published_at, s.collected_at)) AS INTEGER) as week_num,
                       strftime('%Y', COALESCE(s.published_at, s.collected_at)) as yr,
                       COUNT(DISTINCT s.id) as cnt,
                       AVG(sa.score_composite) as avg_score
                FROM signals s
                JOIN signal_analysis sa ON s.id = sa.signal_id
                JOIN signal_bus sb ON s.id = sb.signal_id
                WHERE s.status IN ('scored', 'published')
                  AND COALESCE(s.dismissed, 0) = 0
                  AND COALESCE(s.published_at, s.collected_at) >= ?
                GROUP BY sb.bu_id, week_num, yr
                ORDER BY yr, week_num
            """, (start_date,)).fetchall()

            series_data = defaultdict(lambda: {"name": "", "data": {}})
            all_weeks = set()
            for row in rows:
                bu_id = row[0]
                week_label = f"W{row[1]}"
                all_weeks.add((row[2], row[1], week_label))
                series_data[bu_id]["name"] = bu_names.get(bu_id, bu_id)
                series_data[bu_id]["data"][week_label] = {
                    "count": row[3],
                    "avg_score": round(row[4] or 0, 1),
                }

        # Build ordered week labels
        sorted_weeks = sorted(all_weeks)
        week_labels = [w[2] for w in sorted_weeks]

        # Build final series with data arrays aligned to week_labels
        series = []
        for sid, sdata in series_data.items():
            data_points = []
            for wl in week_labels:
                point = sdata["data"].get(wl, {"count": 0, "avg_score": 0})
                data_points.append(point)
            series.append({
                "id": sid,
                "name": sdata["name"],
                "data": data_points,
            })

        # Sort by total volume descending
        series.sort(key=lambda s: sum(d["count"] for d in s["data"]), reverse=True)

        return {
            "weeks": week_labels,
            "series": series[:10],  # Top 10 lines
        }

    finally:
        if close_conn:
            conn.close()


# ═══════════════════════════════════════════════════════════════════
# V2.4: Competitor Trend Table
# ═══════════════════════════════════════════════════════════════════

def get_competitor_trends(conn=None, bu_code: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None) -> list[dict]:
    """Get competitor signal trends with period-over-period comparison.

    Returns:
        List of competitor dicts with this_period, prior_period, change, trend.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(weeks=4)).strftime("%Y-%m-%d")

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        period_days = (end_dt - start_dt).days
        prior_start = (start_dt - timedelta(days=period_days)).strftime("%Y-%m-%d")
        prior_end = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        bu_clause = ""
        extra_params = []
        if bu_code:
            bu_clause = " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
            extra_params = [bu_code]

        def _count_competitor_signals(comp_name, date_start, date_end):
            params = [f"%{comp_name}%", f"%{comp_name}%",
                      date_start, date_end + " 23:59:59"] + extra_params
            row = conn.execute(f"""
                SELECT COUNT(DISTINCT s.id)
                FROM signals s
                JOIN signal_analysis sa ON s.id = sa.signal_id
                WHERE s.status IN ('scored', 'published')
                  AND COALESCE(s.dismissed, 0) = 0
                  AND (LOWER(s.title) LIKE ? OR LOWER(s.summary) LIKE ?)
                  AND COALESCE(s.published_at, s.collected_at) >= ?
                  AND COALESCE(s.published_at, s.collected_at) <= ?
                  {bu_clause}
            """, params).fetchone()
            return row[0]

        results = []
        for comp in COMPETITORS:
            current = _count_competitor_signals(comp, start_date, end_date)
            prior = _count_competitor_signals(comp, prior_start, prior_end)

            if current == 0 and prior == 0:
                continue

            if prior > 0:
                change_pct = round(((current - prior) / prior) * 100, 1)
            else:
                change_pct = 100.0 if current > 0 else 0

            if change_pct >= 20:
                trend_icon = "rising"
            elif change_pct <= -20:
                trend_icon = "declining"
            else:
                trend_icon = "stable"

            results.append({
                "name": comp.title(),
                "this_period": current,
                "prior_period": prior,
                "change_percent": change_pct,
                "trend": trend_icon,
            })

        # Sort by this_period count descending
        results.sort(key=lambda r: r["this_period"], reverse=True)
        return results

    finally:
        if close_conn:
            conn.close()
