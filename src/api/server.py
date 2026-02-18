"""FastAPI server for VPG Intelligence Digest management UI.

Provides REST API endpoints for:
- Recipient management (add, edit, remove)
- Business unit & industry configuration
- Source management
- Pipeline execution (run digest, dry-run)
- Digest history and status
- Scheduling control

Run with: python -m src.api.server
"""

import logging
import threading
from datetime import datetime
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
    get_recipients,
    get_scoring_weights,
    get_sources,
    save_business_units,
    save_recipients,
    save_scoring_weights,
    save_sources,
)
from src.db import get_connection, init_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="VPG Intelligence Digest",
    description="Management UI for the VPG Weekly Intelligence Digest",
    version="1.0.0",
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
_pipeline_status = {"running": False, "last_result": None, "last_run": None}


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


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None
    tier: int | None = None


class DeliverySettingsUpdate(BaseModel):
    send_day: str | None = None
    send_time_et: str | None = None
    timezone: str | None = None


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


# ── Sources ──────────────────────────────────────────────────────────

@app.get("/api/sources")
def list_sources():
    """Get all configured data sources."""
    return get_sources()


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


# ── Trends ───────────────────────────────────────────────────────────

@app.get("/api/trends")
def list_trends(limit: int = 30):
    """Get current trend summary."""
    from src.trends.tracker import get_trend_summary
    return get_trend_summary(limit=limit)


@app.get("/api/trends/{trend_key}/history")
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


# ── Pipeline Control ─────────────────────────────────────────────────

def _run_pipeline_bg(dry_run: bool = False):
    """Run the pipeline in a background thread."""
    _pipeline_status["running"] = True
    _pipeline_status["last_run"] = datetime.now().isoformat()
    try:
        if dry_run:
            from scripts.dry_run import main as dry_run_main
            dry_run_main()
            _pipeline_status["last_result"] = {"status": "completed", "mode": "dry-run"}
        else:
            from src.pipeline import run_full_pipeline
            result = run_full_pipeline()
            _pipeline_status["last_result"] = result
    except Exception as e:
        _pipeline_status["last_result"] = {"status": "failed", "error": str(e)}
    finally:
        _pipeline_status["running"] = False


@app.post("/api/pipeline/run")
def run_pipeline(dry_run: bool = False):
    """Trigger a pipeline run (live or dry-run).

    Runs asynchronously in the background. Check /api/pipeline/status for results.
    """
    if _pipeline_status["running"]:
        raise HTTPException(409, "Pipeline is already running")

    thread = threading.Thread(target=_run_pipeline_bg, args=(dry_run,), daemon=True)
    thread.start()

    return {
        "message": f"Pipeline started ({'dry-run' if dry_run else 'live'} mode)",
        "status_url": "/api/pipeline/status",
    }


@app.get("/api/pipeline/status")
def pipeline_status():
    """Get the current pipeline status."""
    return _pipeline_status


# ── Digest History ───────────────────────────────────────────────────

@app.get("/api/digests")
def list_digests():
    """List generated digests."""
    MOCK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    digests = []
    for f in sorted(MOCK_OUTPUT_DIR.glob("digest-*.html"), reverse=True):
        stat = f.stat()
        digests.append({
            "filename": f.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "preview_url": f"/api/digests/{f.name}/preview",
        })
    return {"digests": digests}


@app.get("/api/digests/{filename}/preview")
def preview_digest(filename: str):
    """Preview a generated digest HTML."""
    path = MOCK_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Digest not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


# ── Dashboard Stats ──────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    """Get dashboard summary stats."""
    try:
        conn = get_connection()
        init_db()

        signals_total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        signals_scored = conn.execute("SELECT COUNT(*) FROM signals WHERE status='scored'").fetchone()[0]
        pipeline_runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        last_run = conn.execute(
            "SELECT started_at, status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

        conn.close()

        recipients_config = get_recipients()
        active_recipients = sum(
            1 for r in recipients_config.get("recipients", [])
            if r.get("status") == "active"
        )

        digests = list(MOCK_OUTPUT_DIR.glob("digest-*.html")) if MOCK_OUTPUT_DIR.exists() else []

        return {
            "signals_total": signals_total,
            "signals_scored": signals_scored,
            "pipeline_runs": pipeline_runs,
            "last_run": {
                "time": last_run[0] if last_run else None,
                "status": last_run[1] if last_run else None,
            },
            "active_recipients": active_recipients,
            "digests_generated": len(digests),
            "pipeline_running": _pipeline_status["running"],
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
        }


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
