"""Monthly effectiveness report generator for VPG Intelligence Digest.

Auto-generates a monthly summary showing:
- Signals delivered and their breakdown by type, BU, source
- Actions taken (based on feedback and handled flags)
- Estimated pipeline influenced
- Accuracy trends (feedback positive rate over time)
- Source reliability rankings
- Recommendations for next month
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from src.config import get_business_units, get_scoring_weights
from src.db import get_connection

logger = logging.getLogger(__name__)


def generate_monthly_report(year: int = None, month: int = None,
                            conn=None) -> dict:
    """Generate a monthly effectiveness report.

    Args:
        year: Report year (defaults to current/previous month).
        month: Report month (defaults to current/previous month).
        conn: DB connection.

    Returns:
        Dict with full monthly report data.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        now = datetime.now()
        if year is None or month is None:
            # Default to previous month
            first_of_month = now.replace(day=1)
            prev_month = first_of_month - timedelta(days=1)
            year = prev_month.year
            month = prev_month.month

        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        signal_stats = _signal_statistics(conn, start_date, end_date)
        feedback_stats = _feedback_statistics(conn, start_date, end_date)
        pipeline_stats = _pipeline_statistics(conn, start_date, end_date)
        source_rankings = _source_rankings(conn, start_date, end_date)
        bu_coverage = _bu_coverage(conn, start_date, end_date)
        action_stats = _action_statistics(conn, start_date, end_date)
        trend_highlights = _trend_highlights(conn)

        return {
            "period": {
                "year": year,
                "month": month,
                "month_name": datetime(year, month, 1).strftime("%B"),
                "start_date": start_date,
                "end_date": end_date,
            },
            "signal_stats": signal_stats,
            "feedback_stats": feedback_stats,
            "pipeline_stats": pipeline_stats,
            "source_rankings": source_rankings,
            "bu_coverage": bu_coverage,
            "action_stats": action_stats,
            "trend_highlights": trend_highlights,
            "generated_at": datetime.now().isoformat(),
        }

    finally:
        if close_conn:
            conn.close()


def _signal_statistics(conn, start_date: str, end_date: str) -> dict:
    """Compute signal delivery statistics for the period."""
    total = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE collected_at >= ? AND collected_at < ?
    """, (start_date, end_date)).fetchone()[0]

    scored = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE collected_at >= ? AND collected_at < ?
          AND status IN ('scored', 'published')
    """, (start_date, end_date)).fetchone()[0]

    # By signal type
    type_rows = conn.execute("""
        SELECT sa.signal_type, COUNT(*) as cnt, AVG(sa.score_composite) as avg
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.collected_at >= ? AND s.collected_at < ?
        GROUP BY sa.signal_type
        ORDER BY cnt DESC
    """, (start_date, end_date)).fetchall()

    by_type = [
        {"type": r[0], "count": r[1], "avg_score": round(r[2] or 0, 1)}
        for r in type_rows
    ]

    # Average score
    avg_row = conn.execute("""
        SELECT AVG(sa.score_composite), MAX(sa.score_composite)
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.collected_at >= ? AND s.collected_at < ?
    """, (start_date, end_date)).fetchone()

    return {
        "total_collected": total,
        "total_scored": scored,
        "conversion_rate": round(scored / total * 100, 1) if total else 0,
        "avg_score": round(avg_row[0] or 0, 1),
        "max_score": round(avg_row[1] or 0, 1),
        "by_type": by_type,
    }


def _feedback_statistics(conn, start_date: str, end_date: str) -> dict:
    """Compute feedback statistics for the period."""
    total = conn.execute("""
        SELECT COUNT(*) FROM feedback
        WHERE created_at >= ? AND created_at < ?
    """, (start_date, end_date)).fetchone()[0]

    if total == 0:
        return {"total": 0, "positive_rate": 0, "message": "No feedback received this period."}

    positive = conn.execute("""
        SELECT COUNT(*) FROM feedback
        WHERE created_at >= ? AND created_at < ? AND rating = 'up'
    """, (start_date, end_date)).fetchone()[0]

    # Feedback by signal type
    type_rows = conn.execute("""
        SELECT sa.signal_type, f.rating, COUNT(*)
        FROM feedback f
        JOIN signal_analysis sa ON f.signal_id = sa.signal_id
        WHERE f.created_at >= ? AND f.created_at < ?
        GROUP BY sa.signal_type, f.rating
    """, (start_date, end_date)).fetchall()

    type_stats = defaultdict(lambda: {"up": 0, "down": 0})
    for row in type_rows:
        type_stats[row[0]][row[1]] = row[2]

    by_type = {
        st: {
            "positive": stats["up"],
            "negative": stats["down"],
            "rate": round(stats["up"] / (stats["up"] + stats["down"]) * 100, 1)
            if (stats["up"] + stats["down"]) > 0 else 0,
        }
        for st, stats in type_stats.items()
    }

    return {
        "total": total,
        "positive": positive,
        "negative": total - positive,
        "positive_rate": round(positive / total * 100, 1),
        "by_type": by_type,
    }


def _pipeline_statistics(conn, start_date: str, end_date: str) -> dict:
    """Estimate pipeline impact from signals."""
    runs = conn.execute("""
        SELECT COUNT(*), SUM(signals_collected), SUM(signals_scored)
        FROM pipeline_runs
        WHERE started_at >= ? AND started_at < ?
          AND status = 'completed'
    """, (start_date, end_date)).fetchone()

    # Estimate revenue influence from scored signals
    impact_rows = conn.execute("""
        SELECT sa.estimated_impact, sa.score_composite
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.collected_at >= ? AND s.collected_at < ?
          AND s.status IN ('scored', 'published')
          AND sa.score_composite >= 7.0
    """, (start_date, end_date)).fetchall()

    high_impact_count = len(impact_rows)

    return {
        "pipeline_runs": runs[0] or 0,
        "total_collected": runs[1] or 0,
        "total_scored": runs[2] or 0,
        "high_impact_signals": high_impact_count,
        "estimated_pipeline_influence": f"${high_impact_count * 200}K-${high_impact_count * 500}K",
    }


def _source_rankings(conn, start_date: str, end_date: str) -> list[dict]:
    """Rank sources by quality of signals produced."""
    rows = conn.execute("""
        SELECT s.source_name, s.source_tier,
               COUNT(*) as total,
               AVG(sa.score_composite) as avg_score,
               COUNT(CASE WHEN sa.score_composite >= 7.0 THEN 1 END) as high_quality
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.collected_at >= ? AND s.collected_at < ?
        GROUP BY s.source_name
        HAVING total >= 2
        ORDER BY avg_score DESC
    """, (start_date, end_date)).fetchall()

    return [
        {
            "source": r[0],
            "tier": r[1],
            "signal_count": r[2],
            "avg_score": round(r[3] or 0, 1),
            "high_quality_count": r[4],
            "quality_rate": round(r[4] / r[2] * 100, 1) if r[2] else 0,
        }
        for r in rows
    ]


def _bu_coverage(conn, start_date: str, end_date: str) -> list[dict]:
    """Assess signal coverage per BU."""
    bu_config = get_business_units()
    bu_names = {bu["id"]: bu.get("short_name", bu["name"])
                for bu in bu_config.get("business_units", [])}

    rows = conn.execute("""
        SELECT sb.bu_id,
               COUNT(DISTINCT sb.signal_id) as signal_count,
               AVG(sa.score_composite) as avg_score,
               MAX(sa.score_composite) as max_score
        FROM signal_bus sb
        JOIN signals s ON sb.signal_id = s.id
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.collected_at >= ? AND s.collected_at < ?
        GROUP BY sb.bu_id
        ORDER BY signal_count DESC
    """, (start_date, end_date)).fetchall()

    active_bus = {r[0] for r in rows}
    coverage = []

    for r in rows:
        coverage.append({
            "bu_id": r[0],
            "bu_name": bu_names.get(r[0], r[0]),
            "signal_count": r[1],
            "avg_score": round(r[2] or 0, 1),
            "max_score": round(r[3] or 0, 1),
            "status": "active",
        })

    # Add BUs with no signals
    for bu_id, bu_name in bu_names.items():
        if bu_id not in active_bus:
            coverage.append({
                "bu_id": bu_id,
                "bu_name": bu_name,
                "signal_count": 0,
                "avg_score": 0,
                "max_score": 0,
                "status": "no-coverage",
            })

    return coverage


def _action_statistics(conn, start_date: str, end_date: str) -> dict:
    """Track how many signals were acted upon."""
    handled = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE collected_at >= ? AND collected_at < ?
          AND handled = 1
    """, (start_date, end_date)).fetchone()[0]

    dismissed = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE collected_at >= ? AND collected_at < ?
          AND dismissed = 1
    """, (start_date, end_date)).fetchone()[0]

    total_scored = conn.execute("""
        SELECT COUNT(*) FROM signals
        WHERE collected_at >= ? AND collected_at < ?
          AND status IN ('scored', 'published')
    """, (start_date, end_date)).fetchone()[0]

    return {
        "handled": handled,
        "dismissed": dismissed,
        "unactioned": max(0, total_scored - handled - dismissed),
        "action_rate": round(handled / total_scored * 100, 1) if total_scored else 0,
    }


def _trend_highlights(conn) -> list[dict]:
    """Get notable trends for the monthly summary."""
    rows = conn.execute("""
        SELECT label, momentum, occurrence_count, avg_score,
               week_over_week_change
        FROM trends
        WHERE momentum IN ('spike', 'rising')
        ORDER BY avg_score DESC
        LIMIT 5
    """).fetchall()

    return [
        {
            "topic": r[0],
            "momentum": r[1],
            "occurrences": r[2],
            "avg_score": round(r[3] or 0, 1),
            "wow_change": round(r[4] or 0, 1),
        }
        for r in rows
    ]
