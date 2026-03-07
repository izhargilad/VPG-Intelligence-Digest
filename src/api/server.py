"""FastAPI server for VPG Intelligence Digest management UI.

Provides REST API endpoints for:
- Recipient management (add, edit, remove)
- Business unit & industry configuration
- Source management (add, edit, toggle, remove)
- Pipeline execution (run digest, dry-run, pause/resume/cancel)
- Digest history and status
- Delivery schedule editing
- Trend data and history

Run with: python -m src.api.server
"""

import logging
import threading
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import (
    CONFIG_DIR,
    MOCK_OUTPUT_DIR,
    PROJECT_ROOT,
    get_business_units,
    get_industries,
    get_recipients,
    get_scoring_weights,
    get_sources,
    save_business_units,
    save_industries,
    save_recipients,
    save_scoring_weights,
    save_sources,
)
from src.db import (
    get_connection,
    init_db,
    get_all_industries,
    upsert_industry,
    delete_industry as db_delete_industry,
    get_all_keywords,
    upsert_keyword,
    delete_keyword as db_delete_keyword,
    bulk_import_keywords,
    get_pipeline_runs_by_timeframe,
    get_signals_by_timeframe,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="VPG Intelligence Digest",
    description="Management UI for the VPG Weekly Intelligence Digest",
    version="2.3.0",
)

# CORS — allow the React dev server and local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track background pipeline runs
_pipeline_status = {
    "running": False,
    "paused": False,
    "last_result": None,
    "last_run": None,
    "current_stage": "",
}


@app.on_event("startup")
def _startup():
    """Initialize DB, seed industries/keywords from config if empty, clean stale runs."""
    try:
        conn = get_connection()
        init_db()

        # Clean up stale pipeline runs (from prior crash/restart)
        conn.execute(
            "UPDATE pipeline_runs SET status = 'failed', completed_at = datetime('now') "
            "WHERE status = 'running'"
        )
        conn.commit()

        # Auto-seed industries + keywords from config if DB tables are empty
        _auto_seed_industries(conn)

        # Migrate: add dismissed/handled columns to signals if missing (V2.3)
        _migrate_v23(conn)

        conn.close()
    except Exception as e:
        logger.warning("Startup initialization error: %s", e)


def _migrate_v23(conn):
    """Add V2.3 columns (dismissed, handled) to signals + reddit_subreddits table."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
        for col, ddl in [
            ("dismissed", "INTEGER NOT NULL DEFAULT 0"),
            ("dismissed_at", "DATETIME"),
            ("handled", "INTEGER NOT NULL DEFAULT 0"),
            ("handled_at", "DATETIME"),
            ("handled_by", "TEXT DEFAULT ''"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE signals ADD COLUMN {col} {ddl}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reddit_subreddits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at DATETIME NOT NULL DEFAULT (datetime('now')),
                updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        # Seed default subreddits if table is empty
        count = conn.execute("SELECT COUNT(*) FROM reddit_subreddits").fetchone()[0]
        if count == 0:
            from src.collector.reddit_collector import DEFAULT_SUBREDDITS
            _CATEGORIES = {
                "robotics": "Robotics & Automation", "Automate": "Robotics & Automation", "ROS": "Robotics & Automation",
                "aerospace": "Aerospace & Defense", "DefenseIndustry": "Aerospace & Defense",
                "electricvehicles": "Automotive & EV", "SelfDrivingCars": "Automotive & EV", "automotive": "Automotive & EV",
                "metalworking": "Steel & Metals", "manufacturing": "Manufacturing", "Machinists": "Manufacturing",
                "electronics": "Sensors & Instrumentation", "sensors": "Sensors & Instrumentation", "ECE": "Sensors & Instrumentation",
                "materials": "Materials Science", "MaterialsScience": "Materials Science",
                "engineering": "Test & Measurement",
                "SupplyChain": "Trade & Tariffs", "Economics": "Trade & Tariffs",
                "mining": "Mining & Heavy Equipment", "HeavyEquipment": "Mining & Heavy Equipment",
                "agriculture": "Agriculture", "PrecisionAg": "Agriculture", "farming": "Agriculture",
                "SportsScience": "Sports & Performance", "Biomechanics": "Sports & Performance", "sportsmedicine": "Sports & Performance",
                "telecom": "Communication & Telecom", "5G": "Communication & Telecom", "rfelectronics": "Communication & Telecom",
                "Construction": "Infrastructure & Construction", "civilengineering": "Infrastructure & Construction", "infrastructure": "Infrastructure & Construction",
            }
            for sub in DEFAULT_SUBREDDITS:
                cat = _CATEGORIES.get(sub, "General")
                conn.execute(
                    "INSERT OR IGNORE INTO reddit_subreddits (name, category) VALUES (?, ?)",
                    (sub, cat)
                )
            conn.commit()
    except Exception as e:
        logger.warning("V2.3 migration: %s", e)


def _auto_seed_industries(conn):
    """Sync industries and keywords from config/industries.json into DB.

    Uses upsert logic — new industries are added, existing ones are updated.
    This runs on every startup so config file changes are always reflected.
    """
    try:
        config = get_industries()
        config_industries = config.get("industries", [])
        if not config_industries:
            return

        existing_ids = {
            row[0] for row in conn.execute("SELECT id FROM industries").fetchall()
        }
        added = 0
        for ind in config_industries:
            upsert_industry(conn, ind)
            if ind["id"] not in existing_ids:
                added += 1
            # Seed keywords for this industry
            for kw in ind.get("keywords", []):
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO keywords (keyword, industry_id, source) "
                        "VALUES (?, ?, 'seeded')",
                        (kw.lower(), ind["id"]),
                    )
                except Exception:
                    pass
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM industries").fetchone()[0]
        kw_count = conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
        if added > 0:
            logger.info("Synced industries from config: %d new, %d total, %d keywords", added, total, kw_count)
    except Exception as e:
        logger.warning("Could not sync industries: %s", e)


# ── Pydantic Models ──────────────────────────────────────────────────

class RecipientCreate(BaseModel):
    name: str
    email: str
    role: str = ""
    groups: list[str] = ["executive-team"]
    bu_filter: list[str] = ["all"]
    signal_type_filter: list[str] = ["all"]
    notes: str = ""


class RecipientUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    groups: list[str] | None = None
    bu_filter: list[str] | None = None
    signal_type_filter: list[str] | None = None
    status: str | None = None
    notes: str | None = None


class SourceCreate(BaseModel):
    name: str
    url: str
    type: str = "rss"
    tier: int = 2
    relevant_bus: list[str] = []
    keywords: list[str] = []
    is_competitor: bool = False


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None
    tier: int | None = None
    type: str | None = None
    relevant_bus: list[str] | None = None
    keywords: list[str] | None = None
    is_competitor: bool | None = None


class DeliverySettingsUpdate(BaseModel):
    send_day: str | None = None
    send_time_et: str | None = None
    timezone: str | None = None
    max_recipients_per_batch: int | None = None
    batch_delay_seconds: int | None = None


class IndustryCreate(BaseModel):
    id: str
    name: str
    category: str = ""
    description: str = ""
    relevant_bus: list[str] = []
    keywords: list[str] = []
    priority: int = 2
    active: bool = True


class IndustryUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    relevant_bus: list[str] | None = None
    priority: int | None = None
    active: bool | None = None


class KeywordCreate(BaseModel):
    keyword: str
    industry_id: str | None = None
    bu_id: str | None = None
    source: str = "manual"


class KeywordBulkImport(BaseModel):
    keywords: list[str]
    industry_id: str | None = None
    source: str = "imported"


# ── Recipients ───────────────────────────────────────────────────────

@app.get("/api/recipients")
def list_recipients():
    """Get all recipients and delivery settings."""
    return get_recipients()


@app.post("/api/recipients")
def add_recipient(recipient: RecipientCreate):
    """Add a new recipient."""
    config = get_recipients()
    recipients = config.get("recipients", [])

    # Check for duplicate email
    for r in recipients:
        if r["email"] == recipient.email:
            raise HTTPException(400, f"Recipient with email {recipient.email} already exists")

    new_id = f"recipient-{len(recipients) + 1:03d}"
    new_recipient = {
        "id": new_id,
        "name": recipient.name,
        "email": recipient.email,
        "role": recipient.role,
        "groups": recipient.groups,
        "bu_filter": recipient.bu_filter,
        "signal_type_filter": recipient.signal_type_filter,
        "status": "active",
        "created_at": datetime.now().isoformat() + "Z",
        "notes": recipient.notes,
    }
    recipients.append(new_recipient)
    config["recipients"] = recipients
    save_recipients(config)

    return new_recipient


@app.put("/api/recipients/{recipient_id}")
def update_recipient(recipient_id: str, updates: RecipientUpdate):
    """Update an existing recipient."""
    config = get_recipients()
    recipients = config.get("recipients", [])

    for r in recipients:
        if r["id"] == recipient_id:
            update_data = updates.model_dump(exclude_none=True)
            r.update(update_data)
            save_recipients(config)
            return r

    raise HTTPException(404, f"Recipient {recipient_id} not found")


@app.delete("/api/recipients/{recipient_id}")
def delete_recipient(recipient_id: str):
    """Remove a recipient."""
    config = get_recipients()
    recipients = config.get("recipients", [])
    original_len = len(recipients)

    config["recipients"] = [r for r in recipients if r["id"] != recipient_id]

    if len(config["recipients"]) == original_len:
        raise HTTPException(404, f"Recipient {recipient_id} not found")

    save_recipients(config)
    return {"deleted": recipient_id}


@app.get("/api/delivery-settings")
def get_delivery_settings():
    """Get the delivery schedule settings."""
    config = get_recipients()
    return config.get("delivery_settings", {})


@app.put("/api/delivery-settings")
def update_delivery_settings(settings: DeliverySettingsUpdate):
    """Update the delivery schedule settings."""
    config = get_recipients()
    current = config.get("delivery_settings", {})
    update_data = settings.model_dump(exclude_none=True)
    current.update(update_data)
    config["delivery_settings"] = current
    save_recipients(config)
    return current


# ── Business Units ───────────────────────────────────────────────────

@app.get("/api/business-units")
def list_business_units():
    """Get all business units configuration."""
    return get_business_units()


@app.put("/api/business-units/{bu_id}")
def update_business_unit(bu_id: str, updates: dict):
    """Update a business unit's configuration."""
    config = get_business_units()
    for bu in config.get("business_units", []):
        if bu["id"] == bu_id:
            bu.update(updates)
            save_business_units(config)
            return bu
    raise HTTPException(404, f"Business unit {bu_id} not found")


# ── Industries (V2.1) ────────────────────────────────────────────────

@app.get("/api/industries")
def list_industries():
    """Get all industries with BU associations and keyword counts."""
    conn = get_connection()
    try:
        industries = get_all_industries(conn)
        return {"industries": industries}
    except Exception:
        # Table may not exist yet — return from config file
        config = get_industries()
        return {"industries": config.get("industries", [])}
    finally:
        conn.close()


@app.post("/api/industries")
def add_industry(industry: IndustryCreate):
    """Add a new industry to both the DB and config."""
    conn = get_connection()
    try:
        upsert_industry(conn, industry.model_dump())
        # Seed keywords if provided
        if industry.keywords:
            bulk_import_keywords(conn, industry.keywords, industry.id)
        # Sync to config file
        _sync_industries_to_config(conn)
        return {"id": industry.id, "status": "created"}
    finally:
        conn.close()


@app.put("/api/industries/{industry_id}")
def update_industry(industry_id: str, updates: IndustryUpdate):
    """Update an existing industry."""
    conn = get_connection()
    try:
        # Fetch existing
        existing = conn.execute("SELECT * FROM industries WHERE id = ?", (industry_id,)).fetchone()
        if not existing:
            raise HTTPException(404, f"Industry {industry_id} not found")
        merged = dict(existing)
        merged["id"] = industry_id
        update_data = updates.model_dump(exclude_none=True)
        merged.update(update_data)
        # Handle active as int for DB
        if "active" in merged and isinstance(merged["active"], bool):
            pass  # upsert_industry handles the conversion
        upsert_industry(conn, merged)
        _sync_industries_to_config(conn)
        return get_all_industries(conn)
    finally:
        conn.close()


@app.delete("/api/industries/{industry_id}")
def remove_industry(industry_id: str):
    """Delete an industry."""
    conn = get_connection()
    try:
        if not db_delete_industry(conn, industry_id):
            raise HTTPException(404, f"Industry {industry_id} not found")
        _sync_industries_to_config(conn)
        return {"deleted": industry_id}
    finally:
        conn.close()


def _sync_industries_to_config(conn):
    """Write current DB industries back to config/industries.json."""
    industries = get_all_industries(conn)
    # Also fetch keywords per industry for config sync
    for ind in industries:
        kws = get_all_keywords(conn, industry_id=ind["id"])
        ind["keywords"] = [k["keyword"] for k in kws]
        # Clean DB-only fields for config
        for key in ("keyword_count", "created_at", "updated_at"):
            ind.pop(key, None)
        ind["active"] = bool(ind.get("active", 1))
    config = get_industries()
    config["industries"] = industries
    save_industries(config)


# ── Keywords (V2.1) ─────────────────────────────────────────────────

@app.get("/api/keywords")
def list_keywords(industry_id: str | None = None, bu_id: str | None = None):
    """Get keywords, optionally filtered by industry or BU."""
    conn = get_connection()
    try:
        keywords = get_all_keywords(conn, industry_id=industry_id, bu_id=bu_id, active_only=False)
        return {"keywords": keywords}
    finally:
        conn.close()


@app.post("/api/keywords")
def add_keyword(kw: KeywordCreate):
    """Add a single keyword."""
    conn = get_connection()
    try:
        kw_id = upsert_keyword(conn, kw.model_dump())
        return {"id": kw_id, "keyword": kw.keyword}
    finally:
        conn.close()


@app.post("/api/keywords/bulk")
def import_keywords_bulk(data: KeywordBulkImport):
    """Bulk import keywords for an industry."""
    conn = get_connection()
    try:
        count = bulk_import_keywords(conn, data.keywords, data.industry_id, data.source)
        return {"imported": count}
    finally:
        conn.close()


@app.delete("/api/keywords/{keyword_id}")
def remove_keyword(keyword_id: int):
    """Delete a keyword."""
    conn = get_connection()
    try:
        if not db_delete_keyword(conn, keyword_id):
            raise HTTPException(404, f"Keyword {keyword_id} not found")
        return {"deleted": keyword_id}
    finally:
        conn.close()


# ── Keyword Discovery (V2.1 Phase B) ────────────────────────────────

@app.get("/api/keywords/discover")
def discover_keywords(min_score: float = 6.0, max_new: int = 20):
    """Discover new keyword candidates from scored signals (preview only)."""
    from src.analyzer.keyword_discovery import discover_keywords_from_signals
    conn = get_connection()
    try:
        return discover_keywords_from_signals(conn, min_score=min_score, max_new=max_new)
    finally:
        conn.close()


@app.post("/api/keywords/discover/import")
def import_discovered_keywords(min_score: float = 6.0, max_new: int = 20, auto_activate: bool = False):
    """Discover and import new keywords into the database."""
    from src.analyzer.keyword_discovery import auto_import_discovered
    conn = get_connection()
    try:
        return auto_import_discovered(conn, min_score=min_score, max_new=max_new, auto_activate=auto_activate)
    finally:
        conn.close()


@app.post("/api/keywords/update-hits")
def update_keyword_hits():
    """Update keyword hit counts based on recent signal matches."""
    from src.analyzer.keyword_discovery import update_keyword_hit_counts
    conn = get_connection()
    try:
        updated = update_keyword_hit_counts(conn)
        return {"updated": updated}
    finally:
        conn.close()


# ── Google Trends (V2.1 Phase B) ────────────────────────────────────

@app.get("/api/google-trends")
def google_trends_snapshot(keywords: str | None = None, timeframe: str = "now 7-d"):
    """Get a Google Trends snapshot for specified keywords.

    Args:
        keywords: Comma-separated keywords (max 5). Uses industry defaults if empty.
        timeframe: Pytrends timeframe string (e.g., 'now 7-d', 'today 3-m').
    """
    from src.collector.trends_collector import get_trend_snapshot
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()][:5] if keywords else None
    return get_trend_snapshot(keywords=kw_list, timeframe=timeframe)


# ── Sources ──────────────────────────────────────────────────────────

@app.get("/api/sources")
def list_sources():
    """Get all configured data sources."""
    return get_sources()


@app.post("/api/sources")
def add_source(source: SourceCreate):
    """Add a new data source."""
    config = get_sources()
    sources = config.get("sources", [])

    # Generate a URL-safe ID from the name
    slug = source.name.lower().replace(" ", "-").replace(".", "")[:30]
    source_id = slug
    existing_ids = {s["id"] for s in sources}
    counter = 1
    while source_id in existing_ids:
        source_id = f"{slug}-{counter}"
        counter += 1

    new_source = {
        "id": source_id,
        "name": source.name,
        "url": source.url,
        "type": source.type,
        "tier": source.tier,
        "relevant_bus": source.relevant_bus,
        "keywords": source.keywords,
        "active": True,
        "last_check": None,
        "error_count": 0,
    }
    if source.is_competitor:
        new_source["is_competitor"] = True

    sources.append(new_source)
    config["sources"] = sources
    save_sources(config)

    return new_source


@app.put("/api/sources/{source_id}")
def update_source(source_id: str, updates: SourceUpdate):
    """Update a data source."""
    config = get_sources()
    for source in config.get("sources", []):
        if source["id"] == source_id:
            update_data = updates.model_dump(exclude_none=True)
            source.update(update_data)
            save_sources(config)
            return source
    raise HTTPException(404, f"Source {source_id} not found")


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: str):
    """Remove a data source."""
    config = get_sources()
    sources = config.get("sources", [])
    original_len = len(sources)

    config["sources"] = [s for s in sources if s["id"] != source_id]

    if len(config["sources"]) == original_len:
        raise HTTPException(404, f"Source {source_id} not found")

    save_sources(config)
    return {"deleted": source_id}


# ── Trends ───────────────────────────────────────────────────────────

@app.get("/api/trends")
def list_trends(limit: int = 30, start_date: str | None = None, end_date: str | None = None):
    """Get current trend summary, optionally filtered by date range."""
    from src.trends.tracker import get_trend_summary
    return get_trend_summary(limit=limit, start_date=start_date, end_date=end_date)


@app.get("/api/trends/{trend_key:path}/history")
def trend_history(trend_key: str, weeks: int = 12):
    """Get week-by-week history for a specific trend."""
    from src.trends.tracker import get_trend_history
    return {"trend_key": trend_key, "history": get_trend_history(trend_key, weeks)}


# ── Scoring ──────────────────────────────────────────────────────────

@app.get("/api/scoring")
def get_scoring():
    """Get scoring configuration."""
    return get_scoring_weights()


@app.put("/api/scoring")
def update_scoring(weights: dict):
    """Update scoring weights and thresholds."""
    save_scoring_weights(weights)
    return get_scoring_weights()


# ── Export (V2.1 Phase C) ────────────────────────────────────────────

@app.get("/api/export/check")
def export_check():
    """Check which export formats are available (have required packages installed)."""
    excel_ok = False
    pptx_ok = False
    try:
        import openpyxl  # noqa: F401
        excel_ok = True
    except ImportError:
        pass
    try:
        import pptx  # noqa: F401
        pptx_ok = True
    except ImportError:
        pass
    return {
        "excel": {"available": excel_ok, "install": "pip install openpyxl"},
        "pptx": {"available": pptx_ok, "install": "pip install python-pptx"},
    }


@app.get("/api/export/excel")
def export_excel(start_date: str | None = None, end_date: str | None = None,
                 bu_id: str | None = None, signal_type: str | None = None,
                 industry_id: str | None = None, min_score: float = 0):
    """Export signals, trends, and keywords as an Excel workbook with applied filters."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise HTTPException(
            422,
            detail="Excel export requires the 'openpyxl' package. "
                   "Install it with: pip install openpyxl"
        )
    from src.export.excel_export import export_signals_excel
    from fastapi.responses import StreamingResponse
    buffer = export_signals_excel(
        start_date=start_date, end_date=end_date,
        bu_id=bu_id, signal_type=signal_type,
        industry_id=industry_id, min_score=min_score,
    )
    filename = f"vpg-intel-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/export/pptx")
def export_pptx(start_date: str | None = None, end_date: str | None = None,
                bu_id: str | None = None, signal_type: str | None = None,
                industry_id: str | None = None, min_score: float = 0,
                max_signals: int = 10):
    """Export intelligence as a PowerPoint presentation with applied filters."""
    try:
        import pptx  # noqa: F401
    except ImportError:
        raise HTTPException(
            422,
            detail="PowerPoint export requires the 'python-pptx' package. "
                   "Install it with: pip install python-pptx"
        )
    from src.export.pptx_export import export_signals_pptx
    from fastapi.responses import StreamingResponse
    buffer = export_signals_pptx(
        start_date=start_date, end_date=end_date,
        bu_id=bu_id, signal_type=signal_type,
        industry_id=industry_id, min_score=min_score,
        max_signals=max_signals,
    )
    filename = f"vpg-intel-{datetime.now().strftime('%Y%m%d')}.pptx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Intelligence Feed (V2.1 Phase C) ────────────────────────────────

@app.get("/api/feed")
def intelligence_feed(start_date: str | None = None, end_date: str | None = None,
                      bu_id: str | None = None, signal_type: str | None = None,
                      industry_id: str | None = None, min_score: float = 0,
                      limit: int = 50):
    """Get a filterable feed of scored signals with full analysis data.

    Powers the Intelligence Feed UI component.
    """
    conn = get_connection()
    try:
        query = """
            SELECT s.id, s.title, s.url, s.source_name, s.source_tier,
                   s.published_at, s.collected_at, s.image_url,
                   sa.signal_type, sa.headline, sa.what_summary, sa.why_it_matters,
                   sa.quick_win, sa.suggested_owner, sa.estimated_impact,
                   sa.score_composite, sa.score_revenue_impact, sa.score_time_sensitivity,
                   sa.score_strategic_alignment, sa.score_competitive_pressure,
                   sa.validation_level
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND COALESCE(s.dismissed, 0) = 0
        """
        params: list = []

        if min_score > 0:
            query += " AND sa.score_composite >= ?"
            params.append(min_score)
        if start_date:
            query += " AND s.collected_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND s.collected_at <= ?"
            params.append(end_date + " 23:59:59")
        if signal_type:
            query += " AND sa.signal_type = ?"
            params.append(signal_type)
        if bu_id:
            query += " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
            params.append(bu_id)
        if industry_id:
            query += " AND s.id IN (SELECT signal_id FROM signal_industries WHERE industry_id = ?)"
            params.append(industry_id)

        query += " ORDER BY sa.score_composite DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

        # Also fetch source links for each signal (validations)
        signals = []
        for row in rows:
            sig_id = row[0]
            bus = conn.execute(
                "SELECT bu_id FROM signal_bus WHERE signal_id = ?", (sig_id,)
            ).fetchall()
            inds = conn.execute(
                "SELECT industry_id FROM signal_industries WHERE signal_id = ?", (sig_id,)
            ).fetchall()
            sources = conn.execute(
                "SELECT corroborating_url, corroborating_source, corroborating_title "
                "FROM signal_validations WHERE signal_id = ?", (sig_id,)
            ).fetchall()

            signals.append({
                "id": sig_id, "title": row[1], "url": row[2],
                "source_name": row[3], "source_tier": row[4],
                "published_at": row[5], "collected_at": row[6], "image_url": row[7],
                "signal_type": row[8], "headline": row[9],
                "what_summary": row[10], "why_it_matters": row[11],
                "quick_win": row[12], "suggested_owner": row[13],
                "estimated_impact": row[14],
                "score_composite": row[15], "score_revenue_impact": row[16],
                "score_time_sensitivity": row[17], "score_strategic_alignment": row[18],
                "score_competitive_pressure": row[19],
                "validation_level": row[20],
                "bus": [b[0] for b in bus],
                "industries": [i[0] for i in inds],
                "source_links": [{"url": s[0], "source": s[1], "title": s[2]} for s in sources],
                "dismissed": 0,
                "handled": 0,
            })

        return {"signals": signals, "total": len(signals)}
    finally:
        conn.close()


# ── BU Executive Dashboard Data (V2.1 Phase C) ──────────────────────

@app.get("/api/executive/bu-summary")
def bu_executive_summary():
    """Get per-BU signal summary for the executive dashboard."""
    conn = get_connection()
    try:
        bu_config = get_business_units()
        bu_names = {bu["id"]: bu for bu in bu_config.get("business_units", [])}

        # Get signal counts and scores per BU
        rows = conn.execute("""
            SELECT sb.bu_id, COUNT(*) as cnt,
                   AVG(sa.score_composite) as avg_score,
                   MAX(sa.score_composite) as max_score
            FROM signal_bus sb
            JOIN signal_analysis sa ON sb.signal_id = sa.signal_id
            JOIN signals s ON sb.signal_id = s.id
            WHERE s.status IN ('scored', 'published')
            GROUP BY sb.bu_id
            ORDER BY avg_score DESC
        """).fetchall()

        summaries = []
        for row in rows:
            bu_id = row[0]
            bu_info = bu_names.get(bu_id, {})

            # Top signal types for this BU
            type_rows = conn.execute("""
                SELECT sa.signal_type, COUNT(*) as cnt
                FROM signal_bus sb
                JOIN signal_analysis sa ON sb.signal_id = sa.signal_id
                JOIN signals s ON sb.signal_id = s.id
                WHERE sb.bu_id = ? AND s.status IN ('scored', 'published')
                GROUP BY sa.signal_type ORDER BY cnt DESC LIMIT 3
            """, (bu_id,)).fetchall()

            # Top signal for this BU
            top_signal = conn.execute("""
                SELECT sa.headline, sa.score_composite
                FROM signal_bus sb
                JOIN signal_analysis sa ON sb.signal_id = sa.signal_id
                JOIN signals s ON sb.signal_id = s.id
                WHERE sb.bu_id = ? AND s.status IN ('scored', 'published')
                ORDER BY sa.score_composite DESC LIMIT 1
            """, (bu_id,)).fetchone()

            summaries.append({
                "bu_id": bu_id,
                "bu_name": bu_info.get("name", bu_id),
                "bu_short": bu_info.get("short_name", bu_id),
                "color": bu_info.get("color", "#2E75B6"),
                "signal_count": row[1],
                "avg_score": round(row[2] or 0, 1),
                "max_score": round(row[3] or 0, 1),
                "top_types": [{"type": t[0], "count": t[1]} for t in type_rows],
                "top_signal": {
                    "headline": top_signal[0], "score": round(top_signal[1] or 0, 1)
                } if top_signal else None,
            })

        # Overall stats
        total_signals = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE status IN ('scored', 'published')"
        ).fetchone()[0]
        avg_all = conn.execute(
            "SELECT AVG(score_composite) FROM signal_analysis"
        ).fetchone()[0]

        return {
            "bu_summaries": summaries,
            "total_signals": total_signals,
            "overall_avg_score": round(avg_all or 0, 1),
            "bus_with_signals": len(summaries),
            "generated_at": datetime.now().isoformat(),
        }
    finally:
        conn.close()


# ── Pipeline Control ─────────────────────────────────────────────────

def _run_pipeline_bg(dry_run: bool = False, pdf_mode: bool = False):
    """Run the pipeline in a background thread."""
    _pipeline_status["running"] = True
    _pipeline_status["paused"] = False
    _pipeline_status["current_stage"] = ""
    _pipeline_status["last_run"] = datetime.now().isoformat()
    try:
        if dry_run:
            from scripts.dry_run import main as dry_run_main
            dry_run_main(pdf_mode=pdf_mode)
            _pipeline_status["last_result"] = {"status": "completed", "mode": "dry-run", "pdf_generated": pdf_mode}
        else:
            from src.pipeline import run_full_pipeline
            result = run_full_pipeline(pdf_mode=pdf_mode)
            _pipeline_status["last_result"] = result
    except Exception as e:
        _pipeline_status["last_result"] = {"status": "failed", "error": str(e)}
    finally:
        _pipeline_status["running"] = False
        _pipeline_status["paused"] = False
        _pipeline_status["current_stage"] = ""


@app.post("/api/pipeline/run")
def run_pipeline(dry_run: bool = False, pdf_mode: bool = False):
    """Trigger a pipeline run (live or dry-run).

    Args:
        dry_run: If true, use seed data instead of live sources.
        pdf_mode: If true, generate PDF and send as attachment.

    Runs asynchronously in the background. Check /api/pipeline/status for results.
    """
    if _pipeline_status["running"]:
        raise HTTPException(409, "Pipeline is already running")

    thread = threading.Thread(
        target=_run_pipeline_bg,
        args=(dry_run, pdf_mode),
        daemon=True,
    )
    thread.start()

    return {
        "message": f"Pipeline started ({'dry-run' if dry_run else 'live'} mode, "
                   f"{'PDF' if pdf_mode else 'HTML'} delivery)",
        "status_url": "/api/pipeline/status",
    }


@app.post("/api/pipeline/pause")
def pause_pipeline():
    """Pause a running pipeline."""
    if not _pipeline_status["running"]:
        raise HTTPException(400, "Pipeline is not running")

    from src.pipeline import pipeline_control
    pipeline_control.pause()
    _pipeline_status["paused"] = True
    return {"message": "Pipeline paused", "paused": True}


@app.post("/api/pipeline/resume")
def resume_pipeline():
    """Resume a paused pipeline."""
    if not _pipeline_status["running"]:
        raise HTTPException(400, "Pipeline is not running")

    from src.pipeline import pipeline_control
    pipeline_control.resume()
    _pipeline_status["paused"] = False
    return {"message": "Pipeline resumed", "paused": False}


@app.post("/api/pipeline/cancel")
def cancel_pipeline():
    """Cancel a running pipeline."""
    if not _pipeline_status["running"]:
        raise HTTPException(400, "Pipeline is not running")

    from src.pipeline import pipeline_control
    pipeline_control.cancel()
    return {"message": "Pipeline cancellation requested"}


@app.get("/api/pipeline/status")
def pipeline_status():
    """Get the current pipeline status."""
    # Sync stage info from the pipeline control
    if _pipeline_status["running"]:
        try:
            from src.pipeline import pipeline_control
            _pipeline_status["current_stage"] = pipeline_control.current_stage
            _pipeline_status["paused"] = pipeline_control.is_paused
        except Exception:
            pass

    return _pipeline_status


# ── Digest History ───────────────────────────────────────────────────

@app.get("/api/digests")
def list_digests(start_date: str | None = None, end_date: str | None = None):
    """List generated digests (HTML and PDF), optionally filtered by date range."""
    MOCK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    digests = []
    for f in sorted(MOCK_OUTPUT_DIR.glob("digest-*.*"), reverse=True):
        stat = f.stat()
        created = datetime.fromtimestamp(stat.st_mtime)
        # Timeframe filter
        if start_date and created.strftime("%Y-%m-%d") < start_date:
            continue
        if end_date and created.strftime("%Y-%m-%d") > end_date:
            continue
        digests.append({
            "filename": f.name,
            "format": f.suffix.lstrip("."),
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": created.isoformat(),
            "preview_url": f"/api/digests/{f.name}/preview",
        })
    return {"digests": digests}


@app.get("/api/digests/{filename}/preview")
def preview_digest(filename: str):
    """Preview a generated digest (HTML rendered, PDF downloaded)."""
    path = MOCK_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Digest not found")

    if path.suffix == ".pdf":
        return FileResponse(
            str(path),
            media_type="application/pdf",
            filename=path.name,
        )

    return HTMLResponse(path.read_text(encoding="utf-8"))


# ── Dashboard Stats ──────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(start_date: str | None = None, end_date: str | None = None):
    """Get dashboard summary stats, optionally filtered by date range."""
    try:
        conn = get_connection()
        init_db()

        # Build date-filtered signal counts
        sig_query = "SELECT COUNT(*) FROM signals"
        sig_scored_query = "SELECT COUNT(*) FROM signals WHERE status='scored'"
        run_query = "SELECT COUNT(*) FROM pipeline_runs"
        params: list = []
        scored_params: list = []
        run_params: list = []

        if start_date or end_date:
            sig_clauses = []
            scored_clauses = ["status='scored'"]
            run_clauses = []
            if start_date:
                sig_clauses.append("collected_at >= ?")
                params.append(start_date)
                scored_clauses.append("collected_at >= ?")
                scored_params.append(start_date)
                run_clauses.append("started_at >= ?")
                run_params.append(start_date)
            if end_date:
                sig_clauses.append("collected_at <= ?")
                params.append(end_date + " 23:59:59")
                scored_clauses.append("collected_at <= ?")
                scored_params.append(end_date + " 23:59:59")
                run_clauses.append("started_at <= ?")
                run_params.append(end_date + " 23:59:59")
            if sig_clauses:
                sig_query += " WHERE " + " AND ".join(sig_clauses)
            sig_scored_query = "SELECT COUNT(*) FROM signals WHERE " + " AND ".join(scored_clauses)
            if run_clauses:
                run_query += " WHERE " + " AND ".join(run_clauses)

        signals_total = conn.execute(sig_query, params).fetchone()[0]
        signals_scored = conn.execute(sig_scored_query, scored_params).fetchone()[0]
        pipeline_runs_count = conn.execute(run_query, run_params).fetchone()[0]
        last_run = conn.execute(
            "SELECT started_at, status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

        # Industry and keyword counts (V2.1)
        try:
            industries_count = conn.execute("SELECT COUNT(*) FROM industries WHERE active = 1").fetchone()[0]
            keywords_count = conn.execute("SELECT COUNT(*) FROM keywords WHERE active = 1").fetchone()[0]
        except Exception:
            industries_count = 0
            keywords_count = 0

        conn.close()

        recipients_config = get_recipients()
        active_recipients = sum(
            1 for r in recipients_config.get("recipients", [])
            if r.get("status") == "active"
        )

        digests = list(MOCK_OUTPUT_DIR.glob("digest-*.*")) if MOCK_OUTPUT_DIR.exists() else []

        return {
            "signals_total": signals_total,
            "signals_scored": signals_scored,
            "pipeline_runs": pipeline_runs_count,
            "last_run": {
                "time": last_run[0] if last_run else None,
                "status": last_run[1] if last_run else None,
            },
            "active_recipients": active_recipients,
            "digests_generated": len(digests),
            "pipeline_running": _pipeline_status["running"],
            "industries_count": industries_count,
            "keywords_count": keywords_count,
        }
    except Exception as e:
        logger.error("Dashboard query failed: %s", e)
        return {
            "signals_total": 0,
            "signals_scored": 0,
            "pipeline_runs": 0,
            "last_run": {"time": None, "status": None},
            "active_recipients": 0,
            "digests_generated": 0,
            "pipeline_running": False,
            "industries_count": 0,
            "keywords_count": 0,
        }


@app.get("/api/pipeline/runs")
def list_pipeline_runs(start_date: str | None = None, end_date: str | None = None, limit: int = 50):
    """Get pipeline run history with optional date range filter."""
    conn = get_connection()
    try:
        runs = get_pipeline_runs_by_timeframe(conn, start_date, end_date, limit)
        return {"runs": runs}
    finally:
        conn.close()


@app.get("/api/signals")
def list_signals(start_date: str | None = None, end_date: str | None = None,
                 status: str | None = None, limit: int = 100):
    """Get signals with optional date range and status filters."""
    conn = get_connection()
    try:
        signals = get_signals_by_timeframe(conn, start_date, end_date, status)
        return {"signals": signals[:limit], "total": len(signals)}
    finally:
        conn.close()


# ── Recommendations (V2.1 Phase D) ────────────────────────────────

@app.get("/api/recommendations")
def get_recommendations(max_recommendations: int = 15):
    """Generate AI-powered strategic recommendations from signal patterns."""
    from src.analyzer.recommendations import generate_recommendations
    conn = get_connection()
    try:
        return generate_recommendations(conn, max_recommendations=max_recommendations)
    finally:
        conn.close()


# ── Pattern Detection (V2.1 Phase D) ─────────────────────────────

@app.get("/api/patterns")
def get_patterns():
    """Detect recurring patterns across signals, competitors, and trends."""
    from src.analyzer.pattern_detector import detect_patterns
    conn = get_connection()
    try:
        return detect_patterns(conn)
    finally:
        conn.close()


# ── Signal Status Management (V2.3) ─────────────────────────────────

@app.post("/api/signals/{signal_id}/dismiss")
def dismiss_signal(signal_id: int):
    """Mark a signal as not-relevant. Removes from views/stats but kept in DB."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Signal {signal_id} not found")
        conn.execute(
            "UPDATE signals SET dismissed = 1, dismissed_at = datetime('now') WHERE id = ?",
            (signal_id,)
        )
        conn.commit()
        return {"signal_id": signal_id, "dismissed": True}
    finally:
        conn.close()


@app.post("/api/signals/{signal_id}/restore")
def restore_signal(signal_id: int):
    """Restore a previously dismissed signal."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signals SET dismissed = 0, dismissed_at = NULL WHERE id = ?",
            (signal_id,)
        )
        conn.commit()
        return {"signal_id": signal_id, "dismissed": False}
    finally:
        conn.close()


@app.post("/api/signals/{signal_id}/handle")
def handle_signal(signal_id: int, handled_by: str = ""):
    """Mark a signal as read/handled for review tracking."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Signal {signal_id} not found")
        conn.execute(
            "UPDATE signals SET handled = 1, handled_at = datetime('now'), handled_by = ? WHERE id = ?",
            (handled_by, signal_id)
        )
        conn.commit()
        return {"signal_id": signal_id, "handled": True, "handled_by": handled_by}
    finally:
        conn.close()


@app.post("/api/signals/{signal_id}/unhandle")
def unhandle_signal(signal_id: int):
    """Remove handled mark from a signal."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE signals SET handled = 0, handled_at = NULL, handled_by = '' WHERE id = ?",
            (signal_id,)
        )
        conn.commit()
        return {"signal_id": signal_id, "handled": False}
    finally:
        conn.close()


# ── Competitor Pulse (V2.3) ─────────────────────────────────────────

MONITORED_COMPETITORS = [
    "TT Electronics", "HBK", "Hottinger", "Zemic", "Rice Lake",
    "Kistler", "Kyowa", "NMB", "Omega", "Novanta",
    "Flintec", "Sunrise Instruments", "Figure AI", "Boston Dynamics",
    "Mettler Toledo", "Siemens", "Honeywell",
]


@app.get("/api/executive/competitor-pulse")
def competitor_pulse(start_date: str | None = None, end_date: str | None = None,
                     bu_id: str | None = None, industry_id: str | None = None):
    """Top competitors by signal count with trend direction."""
    conn = get_connection()
    try:
        results = []
        for comp in MONITORED_COMPETITORS:
            query = """
                SELECT COUNT(*), AVG(sa.score_composite)
                FROM signals s
                JOIN signal_analysis sa ON s.id = sa.signal_id
                WHERE s.status IN ('scored', 'published')
                  AND COALESCE(s.dismissed, 0) = 0
                  AND (LOWER(s.title) LIKE ? OR LOWER(s.raw_content) LIKE ?
                       OR LOWER(sa.headline) LIKE ? OR LOWER(sa.what_summary) LIKE ?)
            """
            like = f"%{comp.lower()}%"
            params = [like, like, like, like]
            if start_date:
                query += " AND s.collected_at >= ?"
                params.append(start_date)
            if end_date:
                query += " AND s.collected_at <= ?"
                params.append(end_date + " 23:59:59")
            if bu_id:
                query += " AND s.id IN (SELECT signal_id FROM signal_bus WHERE bu_id = ?)"
                params.append(bu_id)
            if industry_id:
                query += " AND s.id IN (SELECT signal_id FROM signal_industries WHERE industry_id = ?)"
                params.append(industry_id)

            row = conn.execute(query, params).fetchone()
            count = row[0] or 0
            if count == 0:
                continue

            # Trend: compare recent 2 weeks vs prior 2 weeks
            recent = conn.execute(
                "SELECT COUNT(*) FROM signals s JOIN signal_analysis sa ON s.id = sa.signal_id "
                "WHERE s.status IN ('scored','published') AND COALESCE(s.dismissed,0)=0 "
                "AND (LOWER(s.title) LIKE ? OR LOWER(sa.headline) LIKE ?) "
                "AND s.collected_at >= date('now', '-14 days')",
                (like, like)
            ).fetchone()[0]
            older = conn.execute(
                "SELECT COUNT(*) FROM signals s JOIN signal_analysis sa ON s.id = sa.signal_id "
                "WHERE s.status IN ('scored','published') AND COALESCE(s.dismissed,0)=0 "
                "AND (LOWER(s.title) LIKE ? OR LOWER(sa.headline) LIKE ?) "
                "AND s.collected_at >= date('now', '-28 days') AND s.collected_at < date('now', '-14 days')",
                (like, like)
            ).fetchone()[0]

            if recent > older:
                trend = "up"
            elif recent < older:
                trend = "down"
            else:
                trend = "stable"

            results.append({
                "competitor": comp,
                "signal_count": count,
                "avg_score": round(row[1] or 0, 1),
                "trend": trend,
                "recent_signals": recent,
            })

        results.sort(key=lambda x: x["signal_count"], reverse=True)
        return {"competitors": results[:10], "total_monitored": len(MONITORED_COMPETITORS)}
    finally:
        conn.close()


# ── Pipeline Last Run (V2.3) ────────────────────────────────────────

@app.get("/api/pipeline/last-run")
def pipeline_last_run():
    """Get the timestamp of the last completed pipeline run."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT started_at, completed_at, status, run_type, signals_collected, signals_scored "
            "FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"last_run": None}
        return {
            "last_run": {
                "started_at": row[0], "completed_at": row[1],
                "status": row[2], "run_type": row[3],
                "signals_collected": row[4], "signals_scored": row[5],
            }
        }
    finally:
        conn.close()


# ── Reddit Subreddit Management (V2.3) ─────────────────────────────

class SubredditCreate(BaseModel):
    name: str
    category: str = ""
    notes: str = ""


class SubredditUpdate(BaseModel):
    category: str | None = None
    active: bool | None = None
    notes: str | None = None


@app.get("/api/reddit/subreddits")
def list_subreddits():
    """Get all managed subreddits."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, category, active, notes, created_at, updated_at "
            "FROM reddit_subreddits ORDER BY category, name"
        ).fetchall()
        subs = []
        for r in rows:
            subs.append({
                "id": r[0], "name": r[1], "category": r[2],
                "active": bool(r[3]), "notes": r[4],
                "created_at": r[5], "updated_at": r[6],
            })
        return {"subreddits": subs, "total": len(subs)}
    finally:
        conn.close()


@app.post("/api/reddit/subreddits")
def add_subreddit(sub: SubredditCreate):
    """Add a new subreddit to monitor."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM reddit_subreddits WHERE name = ?", (sub.name,)
        ).fetchone()
        if existing:
            raise HTTPException(400, f"Subreddit r/{sub.name} already exists")
        conn.execute(
            "INSERT INTO reddit_subreddits (name, category, notes) VALUES (?, ?, ?)",
            (sub.name, sub.category, sub.notes)
        )
        conn.commit()
        return {"name": sub.name, "status": "added"}
    finally:
        conn.close()


@app.put("/api/reddit/subreddits/{sub_id}")
def update_subreddit(sub_id: int, updates: SubredditUpdate):
    """Update a subreddit's settings."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM reddit_subreddits WHERE id = ?", (sub_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Subreddit {sub_id} not found")
        update_data = updates.model_dump(exclude_none=True)
        if "active" in update_data:
            update_data["active"] = int(update_data["active"])
        for key, val in update_data.items():
            conn.execute(
                f"UPDATE reddit_subreddits SET {key} = ?, updated_at = datetime('now') WHERE id = ?",
                (val, sub_id)
            )
        conn.commit()
        return {"id": sub_id, "updated": True}
    finally:
        conn.close()


@app.delete("/api/reddit/subreddits/{sub_id}")
def delete_subreddit(sub_id: int):
    """Remove a subreddit from monitoring."""
    conn = get_connection()
    try:
        deleted = conn.execute("DELETE FROM reddit_subreddits WHERE id = ?", (sub_id,)).rowcount
        conn.commit()
        if not deleted:
            raise HTTPException(404, f"Subreddit {sub_id} not found")
        return {"deleted": sub_id}
    finally:
        conn.close()


# ── Recommendations Export (V2.3) ───────────────────────────────────

@app.get("/api/export/recommendations/excel")
def export_recommendations_excel():
    """Export recommendations as Excel workbook."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise HTTPException(422, detail="Install openpyxl: pip install openpyxl")
    from src.analyzer.recommendations import generate_recommendations
    from fastapi.responses import StreamingResponse

    conn = get_connection()
    try:
        recs_data = generate_recommendations(conn)
    finally:
        conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Recommendations"
    ws.append(["Priority", "Type", "Title", "Description", "Action", "Owner", "Score"])
    priority_map = {1: "Critical", 2: "High", 3: "Medium"}
    for rec in recs_data.get("recommendations", []):
        ws.append([
            priority_map.get(rec.get("priority", 3), "Medium"),
            rec.get("type", ""), rec.get("title", ""),
            rec.get("description", ""), rec.get("action", ""),
            rec.get("owner", ""), rec.get("score", 0),
        ])

    from openpyxl.styles import Font, PatternFill
    navy_fill = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
    for cell in ws[1]:
        cell.fill = navy_fill
        cell.font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"vpg-recommendations-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/export/recommendations/pptx")
def export_recommendations_pptx():
    """Export recommendations as PowerPoint presentation."""
    try:
        import pptx as pptx_mod  # noqa: F401
    except ImportError:
        raise HTTPException(422, detail="Install python-pptx: pip install python-pptx")
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from src.analyzer.recommendations import generate_recommendations
    from fastapi.responses import StreamingResponse

    conn = get_connection()
    try:
        recs_data = generate_recommendations(conn)
    finally:
        conn.close()

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RGBColor(27, 42, 74)
    tb = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(8), Inches(1.5))
    p = tb.text_frame.paragraphs[0]
    p.text = "VPG Strategic Recommendations"
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p2 = tb.text_frame.add_paragraph()
    p2.text = f"Generated {datetime.now().strftime('%B %d, %Y')}"
    p2.font.size = Pt(16)
    p2.font.color.rgb = RGBColor(46, 117, 182)

    priority_colors = {1: RGBColor(229, 57, 53), 2: RGBColor(245, 124, 0), 3: RGBColor(46, 117, 182)}
    priority_labels = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM"}

    for rec in recs_data.get("recommendations", [])[:12]:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        pri = rec.get("priority", 3)
        # Priority badge
        hdr = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.5))
        hp = hdr.text_frame.paragraphs[0]
        r1 = hp.add_run()
        r1.text = f"{priority_labels.get(pri, 'MEDIUM')}  "
        r1.font.size = Pt(11)
        r1.font.bold = True
        r1.font.color.rgb = priority_colors.get(pri, RGBColor(46, 117, 182))
        r2 = hp.add_run()
        r2.text = rec.get("type", "")
        r2.font.size = Pt(11)
        r2.font.color.rgb = RGBColor(100, 100, 100)

        # Title
        ttl = slide.shapes.add_textbox(Inches(0.5), Inches(0.8), Inches(9), Inches(0.8))
        ttl.text_frame.word_wrap = True
        tp = ttl.text_frame.paragraphs[0]
        tp.text = rec.get("title", "")
        tp.font.size = Pt(20)
        tp.font.bold = True
        tp.font.color.rgb = RGBColor(27, 42, 74)

        # Description
        desc = slide.shapes.add_textbox(Inches(0.5), Inches(1.8), Inches(9), Inches(1.5))
        desc.text_frame.word_wrap = True
        dp = desc.text_frame.paragraphs[0]
        dp.text = rec.get("description", "")[:400]
        dp.font.size = Pt(12)
        dp.font.color.rgb = RGBColor(60, 60, 60)

        # Action
        act = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(9), Inches(1.5))
        act.text_frame.word_wrap = True
        ap = act.text_frame.paragraphs[0]
        ar1 = ap.add_run()
        ar1.text = "ACTION: "
        ar1.font.size = Pt(12)
        ar1.font.bold = True
        ar1.font.color.rgb = RGBColor(232, 121, 47)
        ar2 = ap.add_run()
        ar2.text = rec.get("action", "")[:300]
        ar2.font.size = Pt(12)
        ar2.font.color.rgb = RGBColor(60, 60, 60)

    buffer = BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    filename = f"vpg-recommendations-{datetime.now().strftime('%Y%m%d')}.pptx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Serve React Frontend ────────────────────────────────────────────

UI_BUILD_DIR = PROJECT_ROOT / "src" / "ui" / "build"

if UI_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_BUILD_DIR / "static")), name="static")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        """Serve the React SPA for any non-API route."""
        file_path = UI_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(UI_BUILD_DIR / "index.html"))


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server."""
    import uvicorn
    print(f"\n  VPG Intelligence Digest — Management UI")
    print(f"  API:   http://localhost:{port}/api/dashboard")
    print(f"  UI:    http://localhost:{port}")
    print(f"  Docs:  http://localhost:{port}/docs\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
