"""System health monitoring and admin alerting for VPG Intelligence Digest.

Provides a unified health check endpoint that covers:
- Database connectivity
- Source health (Tier 1 failure detection)
- Pipeline execution status
- Delivery success rates
- Configuration validity
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.config import (
    ANTHROPIC_API_KEY,
    CONFIG_DIR,
    DATABASE_PATH,
    DELIVERY_MODE,
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER_EMAIL,
)

logger = logging.getLogger(__name__)


def check_database_health(conn) -> dict:
    """Check database connectivity and basic integrity."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
        signal_count = row[0]
        row = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()
        run_count = row[0]
        return {
            "status": "healthy",
            "signal_count": signal_count,
            "pipeline_runs": run_count,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_config_health() -> dict:
    """Validate required config files exist and are parseable."""
    required_files = [
        "business-units.json",
        "sources.json",
        "recipients.json",
        "scoring-weights.json",
        "industries.json",
    ]
    issues = []
    for fname in required_files:
        path = CONFIG_DIR / fname
        if not path.exists():
            issues.append(f"Missing: {fname}")
        else:
            try:
                import json
                with open(path) as f:
                    json.load(f)
            except Exception as e:
                issues.append(f"Invalid JSON in {fname}: {e}")

    return {
        "status": "healthy" if not issues else "degraded",
        "issues": issues,
    }


def check_credentials_health() -> dict:
    """Check that required credentials are configured."""
    checks = {}
    checks["anthropic_api_key"] = "configured" if ANTHROPIC_API_KEY else "missing"
    checks["delivery_mode"] = DELIVERY_MODE

    if DELIVERY_MODE == "smtp":
        checks["gmail_sender"] = "configured" if GMAIL_SENDER_EMAIL else "missing"
        checks["gmail_app_password"] = "configured" if GMAIL_APP_PASSWORD else "missing"
    elif DELIVERY_MODE == "gmail":
        token_path = CONFIG_DIR / "token.json"
        checks["gmail_oauth_token"] = "present" if token_path.exists() else "missing"

    missing = [k for k, v in checks.items() if v == "missing"]
    return {
        "status": "healthy" if not missing else "degraded",
        "checks": checks,
        "missing": missing,
    }


def check_source_health(conn) -> dict:
    """Check for Tier 1 source failures (3+ consecutive)."""
    # Get sources that have failed 3+ times recently
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    rows = conn.execute(
        """SELECT source_id, COUNT(*) as fail_count
           FROM source_health
           WHERE status != 'success' AND check_time >= ?
           GROUP BY source_id
           HAVING fail_count >= 3
           ORDER BY fail_count DESC""",
        (cutoff,),
    ).fetchall()

    failing_sources = [{"source_id": r["source_id"], "failures": r["fail_count"]} for r in rows]

    total_sources = conn.execute(
        "SELECT COUNT(DISTINCT source_id) FROM source_health WHERE check_time >= ?",
        (cutoff,),
    ).fetchone()[0]

    return {
        "status": "healthy" if not failing_sources else "warning",
        "total_monitored": total_sources,
        "failing_sources": failing_sources,
    }


def check_pipeline_health(conn) -> dict:
    """Check recent pipeline execution health."""
    # Last successful run
    last_success = conn.execute(
        "SELECT started_at, completed_at FROM pipeline_runs WHERE status = 'completed' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    # Failed runs in last 7 days
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    failed_count = conn.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'failed' AND started_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    # Currently running
    running = conn.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'running'"
    ).fetchone()[0]

    result = {
        "status": "healthy",
        "last_success": dict(last_success) if last_success else None,
        "recent_failures": failed_count,
        "currently_running": running,
    }

    if failed_count >= 3:
        result["status"] = "warning"
    if last_success is None:
        result["status"] = "unknown"

    return result


def check_delivery_health(conn) -> dict:
    """Check delivery success rates."""
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()

    total = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE sent_at >= ?", (cutoff,)
    ).fetchone()[0]

    failed = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE status = 'failed' AND sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    if total == 0:
        return {"status": "unknown", "message": "No deliveries in last 7 days"}

    failure_rate = failed / total * 100
    return {
        "status": "healthy" if failure_rate < 20 else "warning",
        "total_attempts": total,
        "failures": failed,
        "failure_rate": round(failure_rate, 1),
    }


def check_disk_health() -> dict:
    """Check disk space for data directory."""
    try:
        import shutil
        usage = shutil.disk_usage(str(DATABASE_PATH.parent))
        free_gb = usage.free / (1024 ** 3)
        used_pct = usage.used / usage.total * 100
        db_size_mb = DATABASE_PATH.stat().st_size / (1024 ** 2) if DATABASE_PATH.exists() else 0

        return {
            "status": "healthy" if free_gb > 1 else "warning",
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_pct, 1),
            "db_size_mb": round(db_size_mb, 2),
        }
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


def get_full_health_check(conn) -> dict:
    """Run all health checks and return aggregate status."""
    checks = {
        "database": check_database_health(conn),
        "config": check_config_health(),
        "credentials": check_credentials_health(),
        "sources": check_source_health(conn),
        "pipeline": check_pipeline_health(conn),
        "delivery": check_delivery_health(conn),
        "disk": check_disk_health(),
    }

    # Overall status: worst of all checks
    statuses = [c["status"] for c in checks.values()]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "warning" in statuses:
        overall = "warning"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    alerts = []
    if checks["sources"]["status"] == "warning":
        for src in checks["sources"].get("failing_sources", []):
            alerts.append({
                "level": "warning",
                "message": f"Source {src['source_id']} has {src['failures']} failures in 7 days",
            })
    if checks["credentials"].get("missing"):
        for m in checks["credentials"]["missing"]:
            alerts.append({"level": "warning", "message": f"Credential missing: {m}"})
    if checks["pipeline"].get("recent_failures", 0) >= 3:
        alerts.append({
            "level": "warning",
            "message": f"{checks['pipeline']['recent_failures']} pipeline failures in 7 days",
        })
    if checks["delivery"].get("failure_rate", 0) >= 20:
        alerts.append({
            "level": "critical",
            "message": f"Delivery failure rate: {checks['delivery']['failure_rate']}%",
        })
    if checks["disk"].get("free_gb", 999) < 1:
        alerts.append({"level": "critical", "message": "Disk space critically low"})

    return {
        "status": overall,
        "timestamp": datetime.now().isoformat(),
        "version": "6.0.0",
        "checks": checks,
        "alerts": alerts,
    }
