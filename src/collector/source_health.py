"""Source health monitoring for VPG Intelligence Digest.

Tracks source reliability, error rates, and last successful collection
to power the source health dashboard.
"""

import logging
from datetime import datetime

from src.config import get_sources
from src.db import get_connection

logger = logging.getLogger(__name__)


def get_source_health(conn=None) -> dict:
    """Get health status for all configured sources.

    Returns:
        Dict with per-source health stats and overall summary.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        sources_config = get_sources()
        sources = sources_config.get("sources", [])

        health_data = []
        for source in sources:
            source_name = source.get("name", "")
            source_id = source.get("id", "")

            # Count signals from this source
            total = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE source_name = ?",
                (source_name,)
            ).fetchone()[0]

            # Count scored signals
            scored = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE source_name = ? AND status IN ('scored', 'published')",
                (source_name,)
            ).fetchone()[0]

            # Last signal collected
            last_signal = conn.execute(
                "SELECT collected_at FROM signals WHERE source_name = ? ORDER BY collected_at DESC LIMIT 1",
                (source_name,)
            ).fetchone()

            # Average score for signals from this source
            avg_score = conn.execute(
                "SELECT AVG(sa.score_composite) FROM signals s "
                "JOIN signal_analysis sa ON s.id = sa.signal_id "
                "WHERE s.source_name = ? AND s.status IN ('scored', 'published')",
                (source_name,)
            ).fetchone()[0]

            # Recent error count (from signal status)
            errors = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE source_name = ? AND status = 'error'",
                (source_name,)
            ).fetchone()[0]

            # Calculate reliability score
            if total > 0:
                reliability = round((total - errors) / total * 100, 1)
            else:
                reliability = 0.0

            # Determine health status
            if total == 0:
                status = "inactive"
            elif errors > total * 0.3:
                status = "unhealthy"
            elif last_signal and (datetime.now() - datetime.fromisoformat(last_signal[0].replace("Z", ""))).days > 14:
                status = "stale"
            else:
                status = "healthy"

            health_data.append({
                "source_id": source_id,
                "source_name": source_name,
                "type": source.get("type", "unknown"),
                "tier": source.get("tier", 3),
                "active": source.get("active", True),
                "total_signals": total,
                "scored_signals": scored,
                "error_count": errors,
                "avg_score": round(avg_score or 0, 1),
                "reliability": reliability,
                "last_signal_at": last_signal[0] if last_signal else None,
                "status": status,
            })

        # Sort: unhealthy first, then by tier
        health_data.sort(key=lambda x: (
            {"unhealthy": 0, "stale": 1, "inactive": 2, "healthy": 3}.get(x["status"], 4),
            x["tier"],
        ))

        # Summary
        active = [h for h in health_data if h["active"]]
        healthy = sum(1 for h in active if h["status"] == "healthy")
        unhealthy = sum(1 for h in active if h["status"] == "unhealthy")
        stale = sum(1 for h in active if h["status"] == "stale")

        return {
            "sources": health_data,
            "summary": {
                "total_sources": len(health_data),
                "active_sources": len(active),
                "healthy": healthy,
                "unhealthy": unhealthy,
                "stale": stale,
                "inactive": len(health_data) - len(active),
                "overall_status": "healthy" if unhealthy == 0 else "degraded" if unhealthy < 3 else "unhealthy",
                "checked_at": datetime.now().isoformat(),
            },
        }

    finally:
        if close_conn:
            conn.close()
