"""Configuration manager for VPG Intelligence Digest.

Loads and provides access to all JSON config files and environment variables.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def _load_json(filename: str) -> dict:
    """Load a JSON config file from the config directory."""
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(filename: str, data: dict) -> None:
    """Save data to a JSON config file in the config directory."""
    path = CONFIG_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_business_units() -> dict:
    """Load business unit configuration."""
    return _load_json("business-units.json")


def get_sources() -> dict:
    """Load source configuration."""
    return _load_json("sources.json")


def get_recipients() -> dict:
    """Load recipient configuration."""
    return _load_json("recipients.json")


def get_scoring_weights() -> dict:
    """Load scoring weights configuration."""
    return _load_json("scoring-weights.json")


def save_business_units(data: dict) -> None:
    """Save business unit configuration."""
    _save_json("business-units.json", data)


def save_sources(data: dict) -> None:
    """Save source configuration."""
    _save_json("sources.json", data)


def save_recipients(data: dict) -> None:
    """Save recipient configuration."""
    _save_json("recipients.json", data)


def save_scoring_weights(data: dict) -> None:
    """Save scoring weights configuration."""
    _save_json("scoring-weights.json", data)


# Environment-based settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
ANTHROPIC_TEMPERATURE = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.3"))
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))

# Gmail settings
GMAIL_SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Delivery mode: 'mock' (local HTML files), 'smtp' (App Password), or 'gmail' (OAuth2 API)
DELIVERY_MODE = os.getenv("DELIVERY_MODE", "mock")
MOCK_OUTPUT_DIR = Path(os.getenv("MOCK_OUTPUT_DIR", str(DATA_DIR / "mock-digests")))

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "vpg_intelligence.db")))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
