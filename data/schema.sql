-- VPG Intelligence Digest - SQLite Database Schema
-- Version: 1.0
-- Created: 2026-02-16

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- Raw signals collected from sources
-- ============================================================
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,               -- Dedup key (hash of url+title)
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    source_id TEXT NOT NULL,               -- References sources.json id
    source_name TEXT NOT NULL,
    source_tier INTEGER NOT NULL DEFAULT 2,
    published_at DATETIME,
    collected_at DATETIME NOT NULL DEFAULT (datetime('now')),
    raw_content TEXT,                       -- Full article text if scraped
    image_url TEXT,                         -- Source article image
    image_local_path TEXT,                  -- Cached local image path
    status TEXT NOT NULL DEFAULT 'new'      -- new, validated, scored, published, archived
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_collected ON signals(collected_at);
CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source_id);

-- ============================================================
-- Validation records linking signals to corroborating sources
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    corroborating_url TEXT NOT NULL,
    corroborating_source TEXT NOT NULL,
    corroborating_title TEXT,
    similarity_score REAL,                  -- How closely the source matches (0-1)
    found_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_validations_signal ON signal_validations(signal_id);

-- ============================================================
-- AI-generated analysis and scoring for each signal
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL UNIQUE REFERENCES signals(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,              -- competitive-threat, revenue-opportunity, etc.
    headline TEXT NOT NULL,
    what_summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    quick_win TEXT NOT NULL,
    suggested_owner TEXT,
    estimated_impact TEXT,                  -- Revenue range string
    outreach_template TEXT,                 -- Optional pre-drafted outreach

    -- Scoring dimensions (1-10 each)
    score_revenue_impact REAL NOT NULL DEFAULT 0,
    score_time_sensitivity REAL NOT NULL DEFAULT 0,
    score_strategic_alignment REAL NOT NULL DEFAULT 0,
    score_competitive_pressure REAL NOT NULL DEFAULT 0,
    score_composite REAL NOT NULL DEFAULT 0,

    -- Validation status
    validation_level TEXT NOT NULL DEFAULT 'unverified',  -- verified, likely, unverified
    source_count INTEGER NOT NULL DEFAULT 1,

    -- AI metadata
    model_used TEXT,
    analyzed_at DATETIME NOT NULL DEFAULT (datetime('now')),
    raw_ai_response TEXT                    -- Full AI response for audit
);

CREATE INDEX IF NOT EXISTS idx_analysis_signal ON signal_analysis(signal_id);
CREATE INDEX IF NOT EXISTS idx_analysis_score ON signal_analysis(score_composite);
CREATE INDEX IF NOT EXISTS idx_analysis_type ON signal_analysis(signal_type);

-- ============================================================
-- Business unit associations for each signal
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_bus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    bu_id TEXT NOT NULL,                    -- References business-units.json id
    relevance_score REAL DEFAULT 0,         -- How relevant to this BU (0-1)
    UNIQUE(signal_id, bu_id)
);

CREATE INDEX IF NOT EXISTS idx_signal_bus_signal ON signal_bus(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_bus_bu ON signal_bus(bu_id);

-- ============================================================
-- Digest records - each weekly digest is logged
-- ============================================================
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    subject_line TEXT NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,
    bu_count INTEGER NOT NULL DEFAULT 0,
    html_content TEXT,                      -- Full rendered HTML
    html_file_path TEXT,                    -- Path to saved HTML file
    status TEXT NOT NULL DEFAULT 'draft',   -- draft, preview, sent, failed
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    sent_at DATETIME,
    UNIQUE(week_number, year)
);

CREATE INDEX IF NOT EXISTS idx_digests_status ON digests(status);

-- ============================================================
-- Delivery tracking per recipient per digest
-- ============================================================
CREATE TABLE IF NOT EXISTS delivery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_id INTEGER NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, sent, failed, bounced
    gmail_message_id TEXT,
    sent_at DATETIME,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_delivery_digest ON delivery_log(digest_id);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery_log(status);

-- ============================================================
-- Feedback from recipients (thumbs up/down on signals)
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    digest_id INTEGER REFERENCES digests(id),
    recipient_email TEXT NOT NULL,
    rating TEXT NOT NULL,                   -- up, down
    comment TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_signal ON feedback(signal_id);

-- ============================================================
-- Source health tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS source_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    check_time DATETIME NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL,                   -- success, error, timeout
    response_time_ms INTEGER,
    signal_count INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_health_source ON source_health(source_id);
CREATE INDEX IF NOT EXISTS idx_source_health_time ON source_health(check_time);

-- ============================================================
-- Execution log for pipeline runs
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,                 -- full, collection, validation, analysis, compose, deliver
    started_at DATETIME NOT NULL DEFAULT (datetime('now')),
    completed_at DATETIME,
    status TEXT NOT NULL DEFAULT 'running', -- running, completed, failed
    signals_collected INTEGER DEFAULT 0,
    signals_validated INTEGER DEFAULT 0,
    signals_scored INTEGER DEFAULT 0,
    digest_id INTEGER REFERENCES digests(id),
    error_message TEXT,
    log_file_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
