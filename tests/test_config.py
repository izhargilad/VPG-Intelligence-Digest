"""Tests for the configuration module."""

import json
from pathlib import Path

import pytest

# Project root for locating config files
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class TestConfigFiles:
    """Test that all config JSON files are valid and complete."""

    def test_business_units_loads(self):
        path = CONFIG_DIR / "business-units.json"
        with open(path) as f:
            data = json.load(f)
        assert "business_units" in data
        assert len(data["business_units"]) == 9

    def test_all_bus_have_required_fields(self):
        path = CONFIG_DIR / "business-units.json"
        with open(path) as f:
            data = json.load(f)
        required = {"id", "name", "key_products", "core_industries", "monitoring_keywords", "active"}
        for bu in data["business_units"]:
            missing = required - set(bu.keys())
            assert not missing, f"BU {bu.get('id', '?')} missing fields: {missing}"

    def test_all_bu_ids_unique(self):
        path = CONFIG_DIR / "business-units.json"
        with open(path) as f:
            data = json.load(f)
        ids = [bu["id"] for bu in data["business_units"]]
        assert len(ids) == len(set(ids)), "Duplicate BU IDs found"

    def test_sources_loads(self):
        path = CONFIG_DIR / "sources.json"
        with open(path) as f:
            data = json.load(f)
        assert "sources" in data
        assert "source_tiers" in data
        assert len(data["sources"]) > 0

    def test_all_sources_have_required_fields(self):
        path = CONFIG_DIR / "sources.json"
        with open(path) as f:
            data = json.load(f)
        required = {"id", "name", "url", "type", "tier", "active"}
        for source in data["sources"]:
            missing = required - set(source.keys())
            assert not missing, f"Source {source.get('id', '?')} missing fields: {missing}"

    def test_recipients_loads(self):
        path = CONFIG_DIR / "recipients.json"
        with open(path) as f:
            data = json.load(f)
        assert "recipients" in data
        assert "recipient_groups" in data
        assert "delivery_settings" in data

    def test_scoring_weights_loads(self):
        path = CONFIG_DIR / "scoring-weights.json"
        with open(path) as f:
            data = json.load(f)
        assert "scoring_dimensions" in data
        assert "signal_types" in data
        assert "thresholds" in data

    def test_scoring_weights_sum_to_one(self):
        path = CONFIG_DIR / "scoring-weights.json"
        with open(path) as f:
            data = json.load(f)
        total = sum(d["weight"] for d in data["scoring_dimensions"].values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_seven_signal_types(self):
        path = CONFIG_DIR / "scoring-weights.json"
        with open(path) as f:
            data = json.load(f)
        assert len(data["signal_types"]) == 7


class TestDatabaseSchema:
    """Test that the database schema file is valid."""

    def test_schema_file_exists(self):
        path = PROJECT_ROOT / "data" / "schema.sql"
        assert path.exists()

    def test_schema_contains_required_tables(self):
        path = PROJECT_ROOT / "data" / "schema.sql"
        schema = path.read_text()
        required_tables = [
            "signals",
            "signal_validations",
            "signal_analysis",
            "signal_bus",
            "digests",
            "delivery_log",
            "feedback",
            "source_health",
            "pipeline_runs",
        ]
        for table in required_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in schema, f"Missing table: {table}"
