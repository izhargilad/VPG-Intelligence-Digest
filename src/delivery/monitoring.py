"""Delivery monitoring and analytics for VPG Intelligence Digest.

Tracks delivery status, logs, per-recipient history, and provides
aggregate analytics for the admin dashboard.
"""

import logging
from datetime import datetime, timedelta

from src.db import get_connection

logger = logging.getLogger(__name__)


def log_delivery(
    conn,
    digest_id: int | None,
    recipient_email: str,
    recipient_name: str = "",
    status: str = "sent",
    gmail_message_id: str = "",
    error_message: str = "",
    retry_count: int = 0,
) -> int:
    """Log a delivery attempt to the delivery_log table."""
    cursor = conn.execute(
        """INSERT INTO delivery_log
           (digest_id, recipient_email, recipient_name, status,
            gmail_message_id, sent_at, error_message, retry_count)
           VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)""",
        (
            digest_id or 0,
            recipient_email,
            recipient_name,
            status,
            gmail_message_id,
            error_message,
            retry_count,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_delivery_stats(conn, days: int = 30) -> dict:
    """Get aggregate delivery statistics for the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    total = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE sent_at >= ?", (cutoff,)
    ).fetchone()[0]

    sent = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE status = 'sent' AND sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    failed = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE status = 'failed' AND sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    bounced = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE status = 'bounced' AND sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    # Unique recipients
    unique_recipients = conn.execute(
        "SELECT COUNT(DISTINCT recipient_email) FROM delivery_log WHERE sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    # Unique digests delivered
    unique_digests = conn.execute(
        "SELECT COUNT(DISTINCT digest_id) FROM delivery_log WHERE status = 'sent' AND sent_at >= ?",
        (cutoff,),
    ).fetchone()[0]

    return {
        "period_days": days,
        "total_attempts": total,
        "sent": sent,
        "failed": failed,
        "bounced": bounced,
        "success_rate": round(sent / total * 100, 1) if total else 0,
        "unique_recipients": unique_recipients,
        "unique_digests": unique_digests,
    }


def get_delivery_logs(
    conn,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    recipient: str | None = None,
) -> list[dict]:
    """Get delivery logs with optional filtering."""
    query = "SELECT * FROM delivery_log WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if recipient:
        query += " AND recipient_email LIKE ?"
        params.append(f"%{recipient}%")

    query += " ORDER BY sent_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_recipient_delivery_history(
    conn, email: str, limit: int = 20
) -> dict:
    """Get delivery history for a specific recipient."""
    rows = conn.execute(
        """SELECT dl.*, d.subject_line, d.week_number, d.year
           FROM delivery_log dl
           LEFT JOIN digests d ON dl.digest_id = d.id
           WHERE dl.recipient_email = ?
           ORDER BY dl.sent_at DESC LIMIT ?""",
        (email, limit),
    ).fetchall()

    deliveries = [dict(r) for r in rows]

    total = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE recipient_email = ?", (email,)
    ).fetchone()[0]
    sent = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE recipient_email = ? AND status = 'sent'",
        (email,),
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM delivery_log WHERE recipient_email = ? AND status = 'failed'",
        (email,),
    ).fetchone()[0]

    return {
        "email": email,
        "total_deliveries": total,
        "successful": sent,
        "failed": failed,
        "success_rate": round(sent / total * 100, 1) if total else 0,
        "recent_deliveries": deliveries,
    }


def get_delivery_timeline(conn, days: int = 30) -> list[dict]:
    """Get daily delivery counts for charting."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        """SELECT DATE(sent_at) as day,
                  COUNT(*) as total,
                  SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
           FROM delivery_log
           WHERE sent_at >= ?
           GROUP BY DATE(sent_at)
           ORDER BY day DESC""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]
