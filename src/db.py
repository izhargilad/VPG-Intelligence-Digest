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
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        _migrate_v24(conn)
    finally:
        conn.close()


def _migrate_v24(conn: sqlite3.Connection) -> None:
    """Add V2.4 columns to existing signals table (safe to re-run)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
    if "version" not in cols:
        conn.execute("ALTER TABLE signals ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    if "first_seen_at" not in cols:
        conn.execute("ALTER TABLE signals ADD COLUMN first_seen_at DATETIME DEFAULT NULL")
        conn.execute("UPDATE signals SET first_seen_at = collected_at WHERE first_seen_at IS NULL")
    conn.commit()


def insert_signal(conn: sqlite3.Connection, signal: dict) -> int:
    """Insert a new signal and return its ID, or 0 if it already exists.

    Uses INSERT OR IGNORE to skip duplicates (same external_id).
    Also uses cursor.rowcount to accurately detect ignored inserts,
    since cursor.lastrowid retains the prior value on IGNORE.
    """
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
    if cursor.rowcount == 0:
        return 0  # Insert was ignored (duplicate external_id)
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


def insert_analysis(conn: sqlite3.Connection, signal_id: int, analysis: dict) -> int:
    """Insert or update the AI analysis for a signal."""
    cursor = conn.execute(
        """INSERT OR REPLACE INTO signal_analysis
           (signal_id, signal_type, headline, what_summary, why_it_matters,
            quick_win, suggested_owner, estimated_impact, outreach_template,
            score_revenue_impact, score_time_sensitivity,
            score_strategic_alignment, score_competitive_pressure,
            score_composite, validation_level, source_count, model_used, raw_ai_response)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            signal_id,
            analysis.get("signal_type", "market-shift"),
            analysis.get("headline", ""),
            analysis.get("what_summary", ""),
            analysis.get("why_it_matters", ""),
            analysis.get("quick_win", ""),
            analysis.get("suggested_owner", ""),
            analysis.get("estimated_impact", ""),
            analysis.get("outreach_template"),
            analysis["scores"].get("revenue_impact", 0),
            analysis["scores"].get("time_sensitivity", 0),
            analysis["scores"].get("strategic_alignment", 0),
            analysis["scores"].get("competitive_pressure", 0),
            analysis.get("composite", 0),
            analysis.get("validation_level", "unverified"),
            analysis.get("source_count", 1),
            analysis.get("analysis_method", "heuristic"),
            None,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def save_signal_bus(conn: sqlite3.Connection, signal_id: int, bu_matches: list[dict]) -> None:
    """Save business unit associations for a signal."""
    for match in bu_matches:
        conn.execute(
            """INSERT OR IGNORE INTO signal_bus (signal_id, bu_id, relevance_score)
               VALUES (?, ?, ?)""",
            (signal_id, match["bu_id"], match.get("relevance_score", 0)),
        )
    conn.commit()


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


# ── Industries (V2.1) ──────────────────────────────────────────────

def get_all_industries(conn: sqlite3.Connection) -> list[dict]:
    """Get all industries with their BU associations and keyword counts."""
    rows = conn.execute(
        "SELECT * FROM industries ORDER BY priority, name"
    ).fetchall()
    industries = []
    for row in rows:
        ind = dict(row)
        # Fetch associated BUs
        bus = conn.execute(
            "SELECT bu_id FROM industry_bus WHERE industry_id = ?", (ind["id"],)
        ).fetchall()
        ind["relevant_bus"] = [b["bu_id"] for b in bus]
        # Keyword count
        kw_count = conn.execute(
            "SELECT COUNT(*) FROM keywords WHERE industry_id = ? AND active = 1",
            (ind["id"],),
        ).fetchone()[0]
        ind["keyword_count"] = kw_count
        industries.append(ind)
    return industries


def upsert_industry(conn: sqlite3.Connection, industry: dict) -> str:
    """Insert or update an industry. Returns the industry id."""
    conn.execute(
        """INSERT INTO industries (id, name, category, description, priority, active, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, category=excluded.category,
             description=excluded.description, priority=excluded.priority,
             active=excluded.active, updated_at=datetime('now')""",
        (
            industry["id"],
            industry["name"],
            industry.get("category", ""),
            industry.get("description", ""),
            industry.get("priority", 2),
            1 if industry.get("active", True) else 0,
        ),
    )
    # Sync BU associations
    conn.execute("DELETE FROM industry_bus WHERE industry_id = ?", (industry["id"],))
    for bu_id in industry.get("relevant_bus", []):
        if bu_id != "all":
            conn.execute(
                "INSERT OR IGNORE INTO industry_bus (industry_id, bu_id) VALUES (?, ?)",
                (industry["id"], bu_id),
            )
    conn.commit()
    return industry["id"]


def delete_industry(conn: sqlite3.Connection, industry_id: str) -> bool:
    """Delete an industry and its BU associations. Returns True if deleted."""
    cursor = conn.execute("DELETE FROM industries WHERE id = ?", (industry_id,))
    conn.commit()
    return cursor.rowcount > 0


# ── Keywords (V2.1) ────────────────────────────────────────────────

def get_all_keywords(conn: sqlite3.Connection, industry_id: str | None = None,
                     bu_id: str | None = None, active_only: bool = True) -> list[dict]:
    """Get keywords, optionally filtered by industry or BU."""
    query = "SELECT * FROM keywords WHERE 1=1"
    params: list = []
    if industry_id:
        query += " AND industry_id = ?"
        params.append(industry_id)
    if bu_id:
        query += " AND bu_id = ?"
        params.append(bu_id)
    if active_only:
        query += " AND active = 1"
    query += " ORDER BY hit_count DESC, keyword"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def upsert_keyword(conn: sqlite3.Connection, keyword: dict) -> int:
    """Insert or update a keyword. Returns the keyword id."""
    existing = conn.execute(
        "SELECT id FROM keywords WHERE keyword = ? AND industry_id IS ?",
        (keyword["keyword"].lower(), keyword.get("industry_id")),
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE keywords SET bu_id = ?, source = ?, active = ?
               WHERE id = ?""",
            (
                keyword.get("bu_id"),
                keyword.get("source", "manual"),
                1 if keyword.get("active", True) else 0,
                existing["id"],
            ),
        )
        conn.commit()
        return existing["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO keywords (keyword, industry_id, bu_id, source, active)
               VALUES (?, ?, ?, ?, ?)""",
            (
                keyword["keyword"].lower(),
                keyword.get("industry_id"),
                keyword.get("bu_id"),
                keyword.get("source", "manual"),
                1 if keyword.get("active", True) else 0,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def delete_keyword(conn: sqlite3.Connection, keyword_id: int) -> bool:
    """Delete a keyword by ID. Returns True if deleted."""
    cursor = conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
    conn.commit()
    return cursor.rowcount > 0


def bulk_import_keywords(conn: sqlite3.Connection, keywords: list[str],
                         industry_id: str | None = None, source: str = "imported") -> int:
    """Bulk import keywords for an industry. Returns count inserted."""
    count = 0
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        try:
            conn.execute(
                "INSERT OR IGNORE INTO keywords (keyword, industry_id, source) VALUES (?, ?, ?)",
                (kw_clean, industry_id, source),
            )
            count += 1
        except Exception:
            pass
    conn.commit()
    return count


# ── Signal ↔ Industry (V2.1) ──────────────────────────────────────

def save_signal_industries(conn: sqlite3.Connection, signal_id: int,
                           industry_matches: list[dict]) -> None:
    """Save industry associations for a signal."""
    for match in industry_matches:
        conn.execute(
            """INSERT OR IGNORE INTO signal_industries
               (signal_id, industry_id, relevance_score, matched_keywords)
               VALUES (?, ?, ?, ?)""",
            (
                signal_id,
                match["industry_id"],
                match.get("relevance_score", 0),
                match.get("matched_keywords", ""),
            ),
        )
    conn.commit()


# ── Timeframe-filtered queries (V2.1) ─────────────────────────────

def get_signals_by_timeframe(conn: sqlite3.Connection, start_date: str | None = None,
                             end_date: str | None = None, status: str | None = None) -> list[dict]:
    """Get signals with optional date range and status filters."""
    query = "SELECT * FROM signals WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if start_date:
        query += " AND collected_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND collected_at <= ?"
        params.append(end_date + " 23:59:59")
    query += " ORDER BY collected_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_pipeline_runs_by_timeframe(conn: sqlite3.Connection, start_date: str | None = None,
                                   end_date: str | None = None, limit: int = 50) -> list[dict]:
    """Get pipeline runs with optional date range filter."""
    query = "SELECT * FROM pipeline_runs WHERE 1=1"
    params: list = []
    if start_date:
        query += " AND started_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND started_at <= ?"
        params.append(end_date + " 23:59:59")
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
