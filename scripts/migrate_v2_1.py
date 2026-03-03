"""V1 → V2.1 database migration script.

Adds the industries, industry_bus, keywords, and signal_industries tables.
Seeds industry and keyword data from config/industries.json.
Safe to run multiple times (uses IF NOT EXISTS / INSERT OR IGNORE).

Usage:
    python -m scripts.migrate_v2_1
"""

import json
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "vpg_intelligence.db"


# ── DDL statements ──────────────────────────────────────────────────

MIGRATION_SQL = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS industries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 2,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS industry_bus (
    industry_id TEXT NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    bu_id TEXT NOT NULL,
    PRIMARY KEY (industry_id, bu_id)
);
CREATE INDEX IF NOT EXISTS idx_industry_bus_bu ON industry_bus(bu_id);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    industry_id TEXT REFERENCES industries(id) ON DELETE SET NULL,
    bu_id TEXT DEFAULT NULL,
    source TEXT DEFAULT 'manual',
    active INTEGER NOT NULL DEFAULT 1,
    hit_count INTEGER NOT NULL DEFAULT 0,
    last_hit_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(keyword, industry_id)
);
CREATE INDEX IF NOT EXISTS idx_keywords_industry ON keywords(industry_id);
CREATE INDEX IF NOT EXISTS idx_keywords_bu ON keywords(bu_id);
CREATE INDEX IF NOT EXISTS idx_keywords_active ON keywords(active);

CREATE TABLE IF NOT EXISTS signal_industries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    industry_id TEXT NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    relevance_score REAL DEFAULT 0,
    matched_keywords TEXT DEFAULT '',
    UNIQUE(signal_id, industry_id)
);
CREATE INDEX IF NOT EXISTS idx_signal_industries_signal ON signal_industries(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_industries_industry ON signal_industries(industry_id);
"""


def run_migration():
    """Execute the V2.1 schema migration and seed data."""
    if not DB_PATH.exists():
        logger.info("Database not found at %s — creating fresh DB from schema.sql", DB_PATH)
        from src.db import init_db
        init_db()
        logger.info("Fresh database created; tables already include V2.1 schema.")
    else:
        logger.info("Applying V2.1 schema migration to %s", DB_PATH)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Apply DDL
    conn.executescript(MIGRATION_SQL)
    conn.commit()
    logger.info("Schema migration applied successfully.")

    # Seed industries from config/industries.json
    industries_path = CONFIG_DIR / "industries.json"
    if not industries_path.exists():
        logger.warning("config/industries.json not found — skipping seed.")
        conn.close()
        return

    with open(industries_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    industries = config.get("industries", [])
    inserted = 0
    kw_inserted = 0

    for ind in industries:
        ind_id = ind["id"]
        try:
            conn.execute(
                """INSERT OR IGNORE INTO industries (id, name, category, description, priority, active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ind_id, ind["name"], ind.get("category", ""), ind.get("description", ""),
                 ind.get("priority", 2), 1 if ind.get("active", True) else 0),
            )
            inserted += conn.total_changes - inserted - kw_inserted
        except sqlite3.IntegrityError:
            pass

        # Industry ↔ BU associations
        for bu_id in ind.get("relevant_bus", []):
            if bu_id == "all":
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO industry_bus (industry_id, bu_id) VALUES (?, ?)",
                    (ind_id, bu_id),
                )
            except sqlite3.IntegrityError:
                pass

        # Keywords
        for kw in ind.get("keywords", []):
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO keywords (keyword, industry_id, source) VALUES (?, ?, 'imported')",
                    (kw.lower(), ind_id),
                )
                kw_inserted += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()

    logger.info("Seeded %d industries and their keywords from config.", len(industries))
    logger.info("Migration complete.")


if __name__ == "__main__":
    run_migration()
