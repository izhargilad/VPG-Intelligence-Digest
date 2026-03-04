"""Pattern detection engine for VPG Intelligence Digest.

Detects recurring patterns across signals over time:
- Competitor clustering: repeated signals about the same competitor
- Topic persistence: themes that keep appearing week after week
- Seasonal patterns: signals that correlate with industry events
- Escalation detection: score trajectories that are accelerating

Runs after scoring to enrich trend data with deeper pattern insights.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime

from src.db import get_connection

logger = logging.getLogger(__name__)

# Minimum signal count to consider a pattern significant
MIN_PATTERN_SIGNALS = 3
# Top N patterns to return per category
MAX_PATTERNS_PER_CATEGORY = 5


def detect_patterns(conn=None) -> dict:
    """Run all pattern detectors and return consolidated results.

    Args:
        conn: DB connection (creates one if None).

    Returns:
        Dict with pattern categories, each containing a list of detected patterns.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        results = {
            "competitor_patterns": _detect_competitor_patterns(conn),
            "topic_persistence": _detect_topic_persistence(conn),
            "score_escalation": _detect_score_escalation(conn),
            "bu_concentration": _detect_bu_concentration(conn),
            "source_patterns": _detect_source_reliability(conn),
            "detected_at": datetime.now().isoformat(),
        }

        total = sum(len(v) for k, v in results.items() if isinstance(v, list))
        results["total_patterns"] = total
        logger.info("Pattern detection complete: %d patterns found", total)
        return results

    finally:
        if close_conn:
            conn.close()


def _detect_competitor_patterns(conn) -> list[dict]:
    """Detect competitor-related signal clustering.

    Looks for competitors appearing across multiple signals,
    indicating sustained competitive activity.
    """
    COMPETITORS = [
        "TT Electronics", "HBK", "Hottinger", "Zemic", "Rice Lake",
        "Kistler", "Kyowa", "NMB", "Omega", "Novanta", "Flintec",
        "Sunrise Instruments", "Figure AI", "Boston Dynamics",
        "Mettler Toledo", "Siemens", "Honeywell",
    ]

    rows = conn.execute("""
        SELECT s.id, s.title, s.summary, sa.score_composite,
               sa.signal_type, s.collected_at
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
        ORDER BY s.collected_at DESC
        LIMIT 500
    """).fetchall()

    competitor_hits = defaultdict(list)
    for row in rows:
        text = f"{row[1]} {row[2] or ''}".lower()
        for comp in COMPETITORS:
            if comp.lower() in text:
                competitor_hits[comp].append({
                    "signal_id": row[0],
                    "title": row[1],
                    "score": row[3] or 0,
                    "type": row[4],
                    "date": row[5],
                })

    patterns = []
    for comp, signals in sorted(competitor_hits.items(),
                                 key=lambda x: len(x[1]), reverse=True):
        if len(signals) < MIN_PATTERN_SIGNALS:
            continue
        avg_score = sum(s["score"] for s in signals) / len(signals)
        types = Counter(s["type"] for s in signals)
        patterns.append({
            "competitor": comp,
            "signal_count": len(signals),
            "avg_score": round(avg_score, 2),
            "dominant_signal_type": types.most_common(1)[0][0] if types else "unknown",
            "latest_date": signals[0]["date"],
            "severity": "high" if avg_score >= 7.5 else "medium" if avg_score >= 5.0 else "low",
            "summary": (
                f"{comp} appeared in {len(signals)} signals "
                f"(avg score {avg_score:.1f}, mostly {types.most_common(1)[0][0].replace('-', ' ') if types else 'N/A'})"
            ),
        })

    return patterns[:MAX_PATTERNS_PER_CATEGORY]


def _detect_topic_persistence(conn) -> list[dict]:
    """Detect topics that persist across multiple weeks.

    Uses trend data to find themes with sustained or growing momentum.
    """
    rows = conn.execute("""
        SELECT t.trend_key, t.label, t.trend_type, t.occurrence_count,
               t.momentum, t.avg_score, t.first_seen, t.last_seen,
               t.week_over_week_change
        FROM trends t
        WHERE t.occurrence_count >= ?
        ORDER BY t.occurrence_count DESC
        LIMIT 20
    """, (MIN_PATTERN_SIGNALS,)).fetchall()

    patterns = []
    for row in rows:
        duration_query = conn.execute(
            "SELECT COUNT(DISTINCT week_number || '-' || year) FROM trend_snapshots WHERE trend_id = ?",
            (conn.execute("SELECT id FROM trends WHERE trend_key = ?", (row[0],)).fetchone() or (0,))[0:1]
        )

        weeks_active = 1
        try:
            trend_id_row = conn.execute(
                "SELECT id FROM trends WHERE trend_key = ?", (row[0],)
            ).fetchone()
            if trend_id_row:
                weeks_row = conn.execute(
                    "SELECT COUNT(DISTINCT week_number || '-' || year) FROM trend_snapshots WHERE trend_id = ?",
                    (trend_id_row[0],)
                ).fetchone()
                weeks_active = weeks_row[0] if weeks_row else 1
        except Exception:
            pass

        patterns.append({
            "topic": row[1],
            "trend_key": row[0],
            "trend_type": row[2],
            "signal_count": row[3],
            "momentum": row[4],
            "avg_score": round(row[5] or 0, 2),
            "first_seen": row[6],
            "last_seen": row[7],
            "weeks_active": max(weeks_active, 1),
            "wow_change": round(row[8] or 0, 1),
            "persistence": "entrenched" if weeks_active >= 4 else "recurring" if weeks_active >= 2 else "emerging",
        })

    return patterns[:MAX_PATTERNS_PER_CATEGORY]


def _detect_score_escalation(conn) -> list[dict]:
    """Detect signal types or BUs with escalating scores.

    Compares recent signal scores to historical averages to identify
    areas where intensity is increasing.
    """
    # Compare recent (7 days) vs older signals per signal_type
    rows = conn.execute("""
        SELECT sa.signal_type,
               AVG(CASE WHEN s.collected_at >= datetime('now', '-7 days')
                        THEN sa.score_composite END) as recent_avg,
               AVG(CASE WHEN s.collected_at < datetime('now', '-7 days')
                        THEN sa.score_composite END) as older_avg,
               COUNT(CASE WHEN s.collected_at >= datetime('now', '-7 days')
                         THEN 1 END) as recent_count,
               COUNT(CASE WHEN s.collected_at < datetime('now', '-7 days')
                         THEN 1 END) as older_count
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
        GROUP BY sa.signal_type
        HAVING recent_count >= 2 AND older_count >= 2
    """).fetchall()

    patterns = []
    for row in rows:
        recent_avg = row[1] or 0
        older_avg = row[2] or 0
        if older_avg == 0:
            continue
        change_pct = ((recent_avg - older_avg) / older_avg) * 100

        if abs(change_pct) < 10:
            continue

        direction = "escalating" if change_pct > 0 else "de-escalating"
        patterns.append({
            "signal_type": row[0],
            "direction": direction,
            "recent_avg_score": round(recent_avg, 2),
            "historical_avg_score": round(older_avg, 2),
            "change_pct": round(change_pct, 1),
            "recent_count": row[3],
            "historical_count": row[4],
            "severity": "high" if abs(change_pct) >= 30 else "medium",
            "summary": (
                f"{row[0].replace('-', ' ').title()} signals are {direction} "
                f"({change_pct:+.1f}%, {recent_avg:.1f} vs {older_avg:.1f} historical avg)"
            ),
        })

    patterns.sort(key=lambda p: abs(p["change_pct"]), reverse=True)
    return patterns[:MAX_PATTERNS_PER_CATEGORY]


def _detect_bu_concentration(conn) -> list[dict]:
    """Detect BUs that are seeing disproportionate signal activity.

    Flags BUs with unusually high or low signal concentration
    relative to the overall distribution.
    """
    from src.config import get_business_units
    bu_config = get_business_units()
    bu_names = {bu["id"]: bu.get("short_name", bu["name"])
                for bu in bu_config.get("business_units", [])}

    rows = conn.execute("""
        SELECT sb.bu_id,
               COUNT(*) as signal_count,
               AVG(sa.score_composite) as avg_score,
               MAX(sa.score_composite) as max_score
        FROM signal_bus sb
        JOIN signals s ON sb.signal_id = s.id
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
          AND s.collected_at >= datetime('now', '-30 days')
        GROUP BY sb.bu_id
        ORDER BY signal_count DESC
    """).fetchall()

    if not rows:
        return []

    total_signals = sum(r[1] for r in rows)
    avg_per_bu = total_signals / max(len(rows), 1)

    patterns = []
    for row in rows:
        count = row[1]
        ratio = count / avg_per_bu if avg_per_bu > 0 else 0

        if ratio < 0.3 or ratio > 2.0:
            concentration = "over-concentrated" if ratio > 2.0 else "under-represented"
            patterns.append({
                "bu_id": row[0],
                "bu_name": bu_names.get(row[0], row[0]),
                "signal_count": count,
                "avg_score": round(row[2] or 0, 2),
                "max_score": round(row[3] or 0, 2),
                "concentration": concentration,
                "ratio": round(ratio, 2),
                "summary": (
                    f"{bu_names.get(row[0], row[0])} is {concentration} with "
                    f"{count} signals ({ratio:.1f}x average)"
                ),
            })

    return patterns[:MAX_PATTERNS_PER_CATEGORY]


def _detect_source_reliability(conn) -> list[dict]:
    """Detect source performance patterns.

    Identifies sources that consistently produce high or low quality signals.
    """
    rows = conn.execute("""
        SELECT s.source_name, s.source_tier,
               COUNT(*) as signal_count,
               AVG(sa.score_composite) as avg_score,
               COUNT(CASE WHEN sa.score_composite >= 7.0 THEN 1 END) as high_quality
        FROM signals s
        JOIN signal_analysis sa ON s.id = sa.signal_id
        WHERE s.status IN ('scored', 'published')
        GROUP BY s.source_name
        HAVING signal_count >= 3
        ORDER BY avg_score DESC
    """).fetchall()

    patterns = []
    for row in rows:
        quality_rate = (row[4] / row[2]) * 100 if row[2] > 0 else 0
        if quality_rate >= 60:
            label = "high-performer"
        elif quality_rate <= 20:
            label = "low-performer"
        else:
            continue  # Average performer, skip

        patterns.append({
            "source_name": row[0],
            "source_tier": row[1],
            "signal_count": row[2],
            "avg_score": round(row[3] or 0, 2),
            "high_quality_rate": round(quality_rate, 1),
            "performance": label,
            "summary": (
                f"{row[0]} (Tier {row[1]}): {label.replace('-', ' ')} — "
                f"{quality_rate:.0f}% high-quality signals ({row[4]}/{row[2]})"
            ),
        })

    return patterns[:MAX_PATTERNS_PER_CATEGORY]
