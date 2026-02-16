"""SQLite database manager for VPG Intelligence Digest.

Handles database initialization, connection management, and common queries.
"""

import sqlite3
from pathlib import Path

from src.config import DATABASE_PATH, DATA_DIR


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Initialize the database by running the schema SQL."""
    schema_path = DATA_DIR / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def insert_signal(conn: sqlite3.Connection, signal: dict) -> int:
    """Insert a new signal and return its ID."""
    cursor = conn.execute(
        """INSERT OR IGNORE INTO signals
           (external_id, title, summary, url, source_id, source_name, source_tier,
            published_at, raw_content, image_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            signal["external_id"],
            signal["title"],
            signal.get("summary"),
            signal["url"],
            signal["source_id"],
            signal["source_name"],
            signal.get("source_tier", 2),
            signal.get("published_at"),
            signal.get("raw_content"),
            signal.get("image_url"),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_signals_by_status(conn: sqlite3.Connection, status: str) -> list[dict]:
    """Get all signals with a given status."""
    cursor = conn.execute(
        "SELECT * FROM signals WHERE status = ? ORDER BY collected_at DESC",
        (status,),
    )
    return [dict(row) for row in cursor.fetchall()]


def update_signal_status(conn: sqlite3.Connection, signal_id: int, status: str) -> None:
    """Update the status of a signal."""
    conn.execute("UPDATE signals SET status = ? WHERE id = ?", (status, signal_id))
    conn.commit()


def insert_validation(conn: sqlite3.Connection, signal_id: int, validation: dict) -> int:
    """Insert a validation record for a signal."""
    cursor = conn.execute(
        """INSERT INTO signal_validations
           (signal_id, corroborating_url, corroborating_source,
            corroborating_title, similarity_score)
           VALUES (?, ?, ?, ?, ?)""",
        (
            signal_id,
            validation["url"],
            validation["source"],
            validation.get("title"),
            validation.get("similarity_score"),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_validation_count(conn: sqlite3.Connection, signal_id: int) -> int:
    """Get the number of corroborating sources for a signal."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM signal_validations WHERE signal_id = ?",
        (signal_id,),
    )
    return cursor.fetchone()[0]


def insert_pipeline_run(conn: sqlite3.Connection, run_type: str) -> int:
    """Start a new pipeline run and return its ID."""
    cursor = conn.execute(
        "INSERT INTO pipeline_runs (run_type) VALUES (?)",
        (run_type,),
    )
    conn.commit()
    return cursor.lastrowid


def complete_pipeline_run(
    conn: sqlite3.Connection, run_id: int, status: str = "completed", **kwargs
) -> None:
    """Mark a pipeline run as completed."""
    sets = ["completed_at = datetime('now')", "status = ?"]
    values = [status]
    for key in ("signals_collected", "signals_validated", "signals_scored", "digest_id", "error_message"):
        if key in kwargs:
            sets.append(f"{key} = ?")
            values.append(kwargs[key])
    values.append(run_id)
    conn.execute(
        f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE id = ?",
        values,
    )
    conn.commit()
