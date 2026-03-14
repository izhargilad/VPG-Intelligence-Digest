"""Config backup and restore for VPG Intelligence Digest.

Provides config validation, backup, and restore capabilities.
"""

import json
import logging
import shutil
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from src.config import CONFIG_DIR, DATA_DIR, DATABASE_PATH

logger = logging.getLogger(__name__)

BACKUP_DIR = DATA_DIR / "backups"

REQUIRED_CONFIG_FILES = [
    "business-units.json",
    "sources.json",
    "recipients.json",
    "scoring-weights.json",
    "industries.json",
]

OPTIONAL_CONFIG_FILES = [
    "competitors.json",
    "partners.json",
    "accounts.json",
    "events.json",
    "keywords.json",
    "products.json",
]


def validate_config() -> dict:
    """Validate all config files for completeness and correctness."""
    results = {"valid": True, "files": {}, "errors": [], "warnings": []}

    for fname in REQUIRED_CONFIG_FILES:
        path = CONFIG_DIR / fname
        if not path.exists():
            results["valid"] = False
            results["errors"].append(f"Required config missing: {fname}")
            results["files"][fname] = {"status": "missing"}
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            results["files"][fname] = {
                "status": "valid",
                "size_bytes": path.stat().st_size,
                "keys": len(data) if isinstance(data, dict) else "N/A",
            }
        except json.JSONDecodeError as e:
            results["valid"] = False
            results["errors"].append(f"Invalid JSON in {fname}: {e}")
            results["files"][fname] = {"status": "invalid", "error": str(e)}

    # BU-specific validation
    bu_path = CONFIG_DIR / "business-units.json"
    if bu_path.exists():
        try:
            with open(bu_path) as f:
                bu_data = json.load(f)
            bus = bu_data.get("business_units", [])
            if len(bus) < 9:
                results["warnings"].append(
                    f"Only {len(bus)} business units configured (expected 9)"
                )
            for bu in bus:
                if not bu.get("id") or not bu.get("name"):
                    results["warnings"].append(
                        f"BU missing id or name: {bu}"
                    )
        except Exception:
            pass

    # Recipient validation
    recip_path = CONFIG_DIR / "recipients.json"
    if recip_path.exists():
        try:
            with open(recip_path) as f:
                recip_data = json.load(f)
            recipients = recip_data.get("recipients", [])
            active = sum(1 for r in recipients if r.get("status") == "active")
            if active == 0:
                results["warnings"].append("No active recipients configured")
        except Exception:
            pass

    # Source validation
    src_path = CONFIG_DIR / "sources.json"
    if src_path.exists():
        try:
            with open(src_path) as f:
                src_data = json.load(f)
            sources = src_data.get("sources", [])
            tier1 = sum(1 for s in sources if s.get("tier") == 1 and s.get("active", True))
            if tier1 == 0:
                results["warnings"].append("No active Tier 1 sources configured")
        except Exception:
            pass

    for fname in OPTIONAL_CONFIG_FILES:
        path = CONFIG_DIR / fname
        if path.exists():
            try:
                with open(path) as f:
                    json.load(f)
                results["files"][fname] = {
                    "status": "valid",
                    "size_bytes": path.stat().st_size,
                }
            except json.JSONDecodeError:
                results["warnings"].append(f"Optional config has invalid JSON: {fname}")

    return results


def create_backup() -> dict:
    """Create a full backup of config files and database."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"vpg_backup_{timestamp}"
    backup_path = BACKUP_DIR / f"{backup_name}.zip"

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Config files
        for fname in REQUIRED_CONFIG_FILES + OPTIONAL_CONFIG_FILES:
            path = CONFIG_DIR / fname
            if path.exists():
                zf.write(path, f"config/{fname}")

        # Database
        if DATABASE_PATH.exists():
            zf.write(DATABASE_PATH, "data/vpg_intelligence.db")

    buf.seek(0)
    backup_path.write_bytes(buf.getvalue())

    size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info("Backup created: %s (%.1f MB)", backup_path, size_mb)

    return {
        "backup_file": str(backup_path),
        "backup_name": backup_name,
        "size_mb": round(size_mb, 2),
        "timestamp": timestamp,
        "files_included": sum(
            1 for f in REQUIRED_CONFIG_FILES + OPTIONAL_CONFIG_FILES
            if (CONFIG_DIR / f).exists()
        ),
        "database_included": DATABASE_PATH.exists(),
    }


def restore_backup(backup_path: str) -> dict:
    """Restore config and database from a backup zip."""
    path = Path(backup_path)
    if not path.exists():
        return {"status": "error", "message": f"Backup not found: {backup_path}"}

    restored_files = []
    with zipfile.ZipFile(path, "r") as zf:
        for entry in zf.namelist():
            if entry.startswith("config/"):
                fname = entry.replace("config/", "")
                target = CONFIG_DIR / fname
                with zf.open(entry) as src:
                    target.write_bytes(src.read())
                restored_files.append(fname)
            elif entry == "data/vpg_intelligence.db":
                # Backup current DB first
                if DATABASE_PATH.exists():
                    bak = DATABASE_PATH.with_suffix(".db.pre_restore")
                    shutil.copy2(DATABASE_PATH, bak)
                with zf.open(entry) as src:
                    DATABASE_PATH.write_bytes(src.read())
                restored_files.append("database")

    return {
        "status": "restored",
        "restored_files": restored_files,
        "source": str(path),
    }


def list_backups() -> list[dict]:
    """List available backups."""
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for f in sorted(BACKUP_DIR.glob("vpg_backup_*.zip"), reverse=True):
        backups.append({
            "name": f.stem,
            "path": str(f),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return backups
