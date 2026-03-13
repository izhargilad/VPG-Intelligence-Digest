"""Feedback-driven scoring refinement for VPG Intelligence Digest.

Analyzes recipient feedback (thumbs-up/down) to:
- Adjust signal type weights based on what recipients find useful
- Identify source quality based on feedback patterns
- Generate feedback-weighted scoring adjustments per BU
- Track feedback effectiveness over time

The refinement is applied as a multiplier on top of the base scoring weights.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime

from src.db import get_connection

logger = logging.getLogger(__name__)

# Minimum feedback count before adjustments are applied
MIN_FEEDBACK_FOR_ADJUSTMENT = 5
# Maximum boost/penalty multiplier
MAX_ADJUSTMENT = 0.3  # ±30% max adjustment


def compute_scoring_adjustments(conn=None) -> dict:
    """Compute scoring adjustments from accumulated feedback.

    Analyzes all feedback to determine which signal types, sources,
    and BUs resonate with recipients, then computes adjustment multipliers.

    Returns:
        Dict with 'signal_type_adjustments', 'source_adjustments',
        'bu_adjustments', and summary stats.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        signal_type_adj = _signal_type_adjustments(conn)
        source_adj = _source_adjustments(conn)
        bu_adj = _bu_adjustments(conn)

        total_feedback = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        positive = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = 'up'"
        ).fetchone()[0]

        return {
            "signal_type_adjustments": signal_type_adj,
            "source_adjustments": source_adj,
            "bu_adjustments": bu_adj,
            "summary": {
                "total_feedback": total_feedback,
                "positive_rate": round(positive / total_feedback * 100, 1) if total_feedback else 0,
                "adjustments_active": total_feedback >= MIN_FEEDBACK_FOR_ADJUSTMENT,
                "computed_at": datetime.now().isoformat(),
            },
        }

    finally:
        if close_conn:
            conn.close()


def get_score_multiplier(signal_type: str, source_name: str, bu_id: str,
                         conn=None) -> float:
    """Get the feedback-based score multiplier for a specific signal.

    Returns a multiplier between 0.7 and 1.3 that adjusts the base score.

    Args:
        signal_type: e.g. 'competitive-threat'
        source_name: Source that produced the signal
        bu_id: Primary BU for the signal

    Returns:
        Score multiplier (1.0 = no adjustment).
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        if total < MIN_FEEDBACK_FOR_ADJUSTMENT:
            return 1.0

        adjustments = compute_scoring_adjustments(conn)

        multiplier = 1.0

        # Signal type adjustment (weighted most heavily)
        type_adj = adjustments["signal_type_adjustments"].get(signal_type, {})
        multiplier += type_adj.get("adjustment", 0) * 0.5

        # Source adjustment
        source_adj = adjustments["source_adjustments"].get(source_name, {})
        multiplier += source_adj.get("adjustment", 0) * 0.3

        # BU adjustment
        bu_adj = adjustments["bu_adjustments"].get(bu_id, {})
        multiplier += bu_adj.get("adjustment", 0) * 0.2

        return max(1.0 - MAX_ADJUSTMENT, min(1.0 + MAX_ADJUSTMENT, multiplier))

    finally:
        if close_conn:
            conn.close()


def _signal_type_adjustments(conn) -> dict:
    """Compute adjustments per signal type based on feedback."""
    rows = conn.execute("""
        SELECT sa.signal_type, f.rating, COUNT(*) as cnt
        FROM feedback f
        JOIN signal_analysis sa ON f.signal_id = sa.signal_id
        GROUP BY sa.signal_type, f.rating
    """).fetchall()

    type_stats = defaultdict(lambda: {"up": 0, "down": 0})
    for row in rows:
        type_stats[row[0]][row[1]] = row[2]

    adjustments = {}
    for signal_type, stats in type_stats.items():
        total = stats["up"] + stats["down"]
        if total < MIN_FEEDBACK_FOR_ADJUSTMENT:
            continue

        positive_rate = stats["up"] / total
        # Adjustment: positive_rate of 0.5 = neutral, >0.5 = boost, <0.5 = penalty
        adjustment = (positive_rate - 0.5) * 2 * MAX_ADJUSTMENT

        adjustments[signal_type] = {
            "positive_rate": round(positive_rate * 100, 1),
            "total_feedback": total,
            "adjustment": round(adjustment, 3),
            "direction": "boost" if adjustment > 0 else "penalty" if adjustment < 0 else "neutral",
        }

    return adjustments


def _source_adjustments(conn) -> dict:
    """Compute adjustments per source based on feedback."""
    rows = conn.execute("""
        SELECT s.source_name, f.rating, COUNT(*) as cnt
        FROM feedback f
        JOIN signals s ON f.signal_id = s.id
        GROUP BY s.source_name, f.rating
    """).fetchall()

    source_stats = defaultdict(lambda: {"up": 0, "down": 0})
    for row in rows:
        source_stats[row[0]][row[1]] = row[2]

    adjustments = {}
    for source, stats in source_stats.items():
        total = stats["up"] + stats["down"]
        if total < 3:  # Lower threshold for sources
            continue

        positive_rate = stats["up"] / total
        adjustment = (positive_rate - 0.5) * 2 * MAX_ADJUSTMENT

        adjustments[source] = {
            "positive_rate": round(positive_rate * 100, 1),
            "total_feedback": total,
            "adjustment": round(adjustment, 3),
        }

    return adjustments


def _bu_adjustments(conn) -> dict:
    """Compute adjustments per BU based on feedback."""
    rows = conn.execute("""
        SELECT sb.bu_id, f.rating, COUNT(*) as cnt
        FROM feedback f
        JOIN signal_bus sb ON f.signal_id = sb.signal_id
        GROUP BY sb.bu_id, f.rating
    """).fetchall()

    bu_stats = defaultdict(lambda: {"up": 0, "down": 0})
    for row in rows:
        bu_stats[row[0]][row[1]] = row[2]

    adjustments = {}
    for bu_id, stats in bu_stats.items():
        total = stats["up"] + stats["down"]
        if total < MIN_FEEDBACK_FOR_ADJUSTMENT:
            continue

        positive_rate = stats["up"] / total
        adjustment = (positive_rate - 0.5) * 2 * MAX_ADJUSTMENT

        adjustments[bu_id] = {
            "positive_rate": round(positive_rate * 100, 1),
            "total_feedback": total,
            "adjustment": round(adjustment, 3),
        }

    return adjustments


def get_feedback_summary(conn=None) -> dict:
    """Get a summary of all feedback for the dashboard.

    Returns:
        Dict with overall stats, per-type breakdown, trending, etc.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        if total == 0:
            return {
                "total_feedback": 0,
                "message": "No feedback collected yet.",
            }

        positive = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = 'up'"
        ).fetchone()[0]

        recent = conn.execute("""
            SELECT f.signal_id, sa.headline, f.rating, f.created_at
            FROM feedback f
            JOIN signal_analysis sa ON f.signal_id = sa.signal_id
            ORDER BY f.created_at DESC LIMIT 10
        """).fetchall()

        by_type = conn.execute("""
            SELECT sa.signal_type, f.rating, COUNT(*)
            FROM feedback f
            JOIN signal_analysis sa ON f.signal_id = sa.signal_id
            GROUP BY sa.signal_type, f.rating
            ORDER BY sa.signal_type
        """).fetchall()

        type_breakdown = defaultdict(lambda: {"up": 0, "down": 0})
        for row in by_type:
            type_breakdown[row[0]][row[1]] = row[2]

        return {
            "total_feedback": total,
            "positive": positive,
            "negative": total - positive,
            "positive_rate": round(positive / total * 100, 1),
            "type_breakdown": dict(type_breakdown),
            "recent_feedback": [
                {
                    "signal_id": r[0],
                    "headline": r[1],
                    "rating": r[2],
                    "created_at": r[3],
                }
                for r in recent
            ],
        }

    finally:
        if close_conn:
            conn.close()
