# VPG Intelligence Platform V2 — Claude Code Development Brief

**Build on top of the existing V1 Weekly Intelligence Digest codebase.**  
**Read CLAUDE.md and BRIEF.md for V1 context before starting.**

---

## V2 Overview

V2 transforms the V1 email digest into a full market intelligence platform by adding:
1. **Structured signal database** with queryable storage for all historical signals
2. **Executive dashboard** with real-time views, trends, and AI recommendations
3. **Reddit monitoring** as a new social signal source
4. **Google Trends integration** for demand sensing and trend validation
5. **Proactive AI recommendations** engine based on accumulated intelligence patterns

All V1 functionality (weekly email digest, source validation, action cards, Gmail delivery) must continue working unchanged.

---

## 1. Structured Signal Database

### 1.1 Database Schema Evolution

Migrate from the V1 SQLite schema to a richer structure. All existing data must be preserved.

**Core Tables:**

```sql
-- Signals: Every detected signal, validated or not
signals (
  id TEXT PRIMARY KEY,
  created_at DATETIME,
  updated_at DATETIME,
  headline TEXT NOT NULL,
  summary TEXT,
  signal_type TEXT NOT NULL,  -- competitive_threat, revenue_opportunity, market_shift, partnership_signal, customer_intelligence, technology_trend, trade_tariff
  source_channel TEXT,        -- rss, web_scrape, reddit, google_trends, api
  validation_status TEXT,     -- verified, likely, unverified
  validation_source_count INTEGER,
  composite_score REAL,
  score_revenue_impact REAL,
  score_time_sensitivity REAL,
  score_strategic_alignment REAL,
  score_competitive_pressure REAL,
  why_it_matters TEXT,
  quick_win_action TEXT,
  suggested_owner_role TEXT,
  estimated_impact_range TEXT,
  outreach_template TEXT,
  included_in_digest_id TEXT,   -- NULL if not yet included
  digest_week_number INTEGER,
  raw_content TEXT,             -- Original scraped/collected text
  metadata JSON                 -- Flexible field for source-specific data
)

-- Signal-to-BU mapping (many-to-many)
signal_bus (
  signal_id TEXT REFERENCES signals(id),
  bu_code TEXT,               -- force_sensors, foil_resistors, micro_measurements, onboard_weighing, blh_nobel, kelk, gleeble, pacific_instruments, dts
  relevance_score REAL,
  PRIMARY KEY (signal_id, bu_code)
)

-- Signal-to-Industry mapping
signal_industries (
  signal_id TEXT REFERENCES signals(id),
  industry TEXT,
  PRIMARY KEY (signal_id, industry)
)

-- Signal-to-Company mapping (track which companies each signal mentions)
signal_companies (
  signal_id TEXT REFERENCES signals(id),
  company_name TEXT,
  company_type TEXT,          -- competitor, customer, partner, prospect, oem
  PRIMARY KEY (signal_id, company_name)
)

-- Sources: Track each source URL with its validation role
signal_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT REFERENCES signals(id),
  url TEXT NOT NULL,
  title TEXT,
  publisher TEXT,
  published_date DATETIME,
  source_tier INTEGER,        -- 1, 2, or 3
  is_primary BOOLEAN DEFAULT FALSE
)

-- Digests: Archive of every sent digest
digests (
  id TEXT PRIMARY KEY,
  week_number INTEGER,
  year INTEGER,
  date_range_start DATE,
  date_range_end DATE,
  sent_at DATETIME,
  recipient_count INTEGER,
  signal_count INTEGER,
  html_content TEXT,          -- Full HTML archive
  executive_summary TEXT
)

-- Reddit-specific tracking
reddit_signals (
  signal_id TEXT REFERENCES signals(id),
  subreddit TEXT,
  post_id TEXT,
  post_title TEXT,
  post_url TEXT,
  upvotes INTEGER,
  comment_count INTEGER,
  author TEXT,
  flair TEXT,
  sentiment_score REAL,       -- -1.0 to 1.0
  relevance_confidence REAL,  -- 0.0 to 1.0, must be >0.7 to include
  collected_at DATETIME
)

-- Google Trends tracking
trends_data (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  keyword TEXT,
  bu_code TEXT,
  date DATE,
  interest_value REAL,        -- Google Trends scaled value
  geo TEXT DEFAULT 'US',
  timeframe TEXT,
  related_queries JSON,
  rising_queries JSON,
  collected_at DATETIME
)

-- Feedback tracking (from email thumbs up/down)
signal_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT REFERENCES signals(id),
  recipient_email TEXT,
  rating TEXT,                -- thumbs_up, thumbs_down
  timestamp DATETIME
)

-- AI Recommendations log
ai_recommendations (
  id TEXT PRIMARY KEY,
  created_at DATETIME,
  recommendation_type TEXT,   -- trend_alert, competitor_strategy, cross_bu_opportunity, persistent_signal
  title TEXT,
  description TEXT,
  supporting_signal_ids JSON, -- Array of signal IDs
  target_bus JSON,            -- Array of BU codes
  priority TEXT,              -- critical, high, medium, low
  status TEXT,                -- new, acknowledged, acted_on, dismissed
  acknowledged_by TEXT,
  acted_on_at DATETIME
)
```

### 1.2 Data Migration

Write a migration script that:
1. Reads existing V1 signals from the current database
2. Maps them to the new schema
3. Preserves all historical data
4. Runs idempotently (safe to re-run)

---

## 2. Reddit Monitoring Module

### 2.1 API Configuration

**Authentication:** Reddit OAuth2 (free tier)
- Register app at reddit.com/prefs/apps (type: "script")
- Rate limit: 100 requests/minute per OAuth client
- Use proper User-Agent: `vpg-intelligence:v2.0 (by /u/YOUR_REDDIT_USERNAME)`
- Store credentials in `.env` (never in repo)

**Python library:** Use PRAW (Python Reddit API Wrapper) — mature, handles rate limiting automatically.

```
pip install praw
```

### 2.2 Subreddit Monitoring List

Pre-configure these subreddits, organized by VPG BU relevance:

| Subreddit | Members (approx) | Relevant BUs | Signal Types |
|-----------|-----------------|-------------|-------------|
| r/robotics | 600K+ | Force Sensors, Micro-Measurements | Technology trends, product discussions |
| r/engineering | 500K+ | All BUs | Industry discussions, career signals |
| r/AskEngineers | 300K+ | All BUs | Product recommendations, vendor complaints |
| r/manufacturing | 50K+ | Force Sensors, BLH Nobel, KELK | Process discussions, equipment needs |
| r/PLC | 100K+ | Force Sensors, BLH Nobel | Automation projects, sensor discussions |
| r/aerospace | 100K+ | Foil Resistors, Pacific Instruments, DTS, Micro-Measurements | Defense/space projects, testing needs |
| r/metallurgy | 30K+ | KELK, Gleeble | Materials research, process discussions |
| r/AutomotiveEngineering | 30K+ | DTS, Micro-Measurements | Crash testing, vehicle development |
| r/semiconductors | 50K+ | Foil Resistors | Industry news, equipment discussions |
| r/trucking | 200K+ | Onboard Weighing | Compliance, weight regulations |
| r/mining | 20K+ | Onboard Weighing, BLH Nobel | Equipment, payload discussions |
| r/3Dprinting | 1M+ | Force Sensors | Sensor integration, precision applications |
| r/MechanicalEngineering | 200K+ | All BUs | Strain measurement, testing discussions |
| r/defense | 50K+ | Foil Resistors, Pacific Instruments, DTS | Defense procurement, program signals |

**This list must be configurable via the web UI** (Tab 1 of the config interface — add a sub-tab for Reddit sources).

### 2.3 Collection Strategy

**CRITICAL: Reddit is noisy. Aggressive filtering is mandatory.**

Collection runs: 3x per week (Monday, Wednesday, Friday — staggered from the main Saturday collection)

**Step 1: Keyword Search**
For each monitored subreddit, search for posts containing VPG-relevant keywords:
- Product keywords: "load cell", "strain gage", "force sensor", "torque sensor", "data acquisition", "weighing system", "foil resistor", "thickness measurement"
- Competitor keywords: "HBK", "Kistler", "Zemic", "TT Electronics", "Rice Lake", "Flintec"
- Problem keywords: "recommend sensor", "looking for", "alternative to", "problems with", "accuracy issues", "calibration", "need help choosing"
- Technology keywords: "humanoid robot", "cobot", "crash test", "rolling mill", "strain measurement"

**Step 2: Relevance Filtering (AI-Powered)**
Every Reddit post that matches keywords goes through Claude Sonnet for relevance scoring:
- Relevance confidence score: 0.0 to 1.0
- **Only include signals with relevance_confidence > 0.7**
- Score based on: Does this discuss a product/technology VPG sells or competes with? Does this indicate a buying signal, complaint, or technology need? Is this from a professional context (not a hobbyist/student)?
- Explicitly filter out: homework/student questions, hobbyist projects below commercial relevance, memes, jokes, off-topic discussions

**Step 3: Sentiment Analysis**
For relevant posts, analyze sentiment (-1.0 to 1.0):
- Negative sentiment about competitors = Revenue Opportunity signal
- Positive sentiment about VPG-relevant technologies = Market Validation signal
- Frustrated "looking for alternatives" = Direct Sales Lead signal

**Step 4: Engagement Scoring**
Weight signals by Reddit engagement:
- Post upvotes > 50 = high community validation
- Comment count > 20 = active discussion (higher signal value)
- Posts from verified industry professionals (flair, post history) get boosted

### 2.4 Reddit Signal Card Format

Reddit signals get a modified Action Card with additional context:

```
┌──────────────────────────────────────────────────────────┐
│ 🔴 REDDIT SIGNAL  [Headline]              [SCORE: 7.2]  │
│ BU: VPG Force Sensors | r/robotics | 127 upvotes        │
│──────────────────────────────────────────────────────────│
│ WHAT: Summary of the discussion/post                     │
│ ORIGINAL POST: [Direct Reddit link]                      │
│ SENTIMENT: Negative toward [Competitor] / Positive need  │
│ WHY IT MATTERS: Maps to VPG capability                   │
│ QUICK WIN: Specific outreach or content action            │
│ CONFIDENCE: 0.85 (Verified by community engagement)      │
│ ⚠ SOURCE: Reddit (treat as informal / unverified claim)  │
└──────────────────────────────────────────────────────────┘
```

**Important:** Reddit signals should always carry a visual indicator that they are from an informal source. They should not be weighted equally with verified industry sources unless corroborated by traditional sources.

---

## 3. Google Trends Integration

### 3.1 Implementation Approach

**Dual-path strategy:**

1. **Primary (if approved):** Google Trends API (alpha) — apply at developers.google.com/search/apis/trends
   - Consistently scaled data (not 0-100 per request)
   - Compare dozens of terms simultaneously
   - Daily/weekly/monthly aggregations
   - 1800-day rolling window

2. **Fallback (immediate):** pytrends library
   - `pip install pytrends`
   - Well-established, works today
   - Data scaled 0-100 per request (requires normalization for cross-request comparison)
   - Rate-limited by Google (implement delays between requests)

**Start with pytrends immediately. Switch to official API when access is granted.**

### 3.2 Keywords to Track

Organize tracking keywords by BU:

```json
{
  "force_sensors": ["load cell", "force transducer", "torque sensor", "force measurement", "load cell manufacturer"],
  "foil_resistors": ["precision resistor", "foil resistor", "current sense resistor", "Z-foil resistor"],
  "micro_measurements": ["strain gage", "strain gauge", "stress analysis sensor", "structural health monitoring"],
  "onboard_weighing": ["onboard weighing system", "truck weighing", "payload monitoring", "vehicle weight compliance"],
  "blh_nobel": ["process weighing", "industrial load cell", "batch weighing system"],
  "kelk": ["rolling mill measurement", "strip thickness measurement", "laser thickness gauge"],
  "gleeble": ["Gleeble", "thermal mechanical simulator", "materials testing equipment"],
  "pacific_instruments": ["high channel data acquisition", "signal conditioning system"],
  "dts": ["crash test data acquisition", "miniature data recorder", "impact data acquisition"],
  "competitors": ["HBK sensors", "Kistler sensor", "Zemic load cell", "TT Electronics resistor", "Rice Lake weighing"],
  "markets": ["industrial automation sensors", "humanoid robot sensors", "aerospace testing equipment", "automotive crash testing"]
}
```

**Also track rising/related queries** — these often reveal emerging applications or competitor products before they appear in trade press.

### 3.3 Trends Data Collection Schedule

- **Weekly full scan:** Every Saturday (alongside main collection), pull interest-over-time for all keywords, last 7 days
- **Monthly deep scan:** First Saturday of each month, pull 90-day trends for comparison and rising query detection
- **Quarterly benchmark:** Compare 12-month trends across all BUs for executive reporting

### 3.4 Trends Integration into Digest

Add a new digest section: **"Search Demand Radar"**

For each BU, show:
- Top 3 keywords trending up (with % change vs. prior week)
- Top 3 keywords trending down
- Notable rising related queries (potential new market signals)
- Geographic hotspots (regions with surging interest)

Format as a simple, scannable table — not charts (HTML email rendering limitations).

---

## 4. Executive Dashboard

### 4.1 Technology

Build as a React + Tailwind web application, served by the same backend as the Config UI.

**Extend the existing Config UI** with new dashboard tabs rather than creating a separate application. Add navigation:
- **Dashboard** (new — default landing page)
- **Intelligence Feed** (new — real-time signal stream)
- **Trends** (new — Google Trends visualizations)
- **Configuration** (existing — BUs, Recipients, Sources, Reddit)
- **Archive** (existing — digest history, enhanced with search)

### 4.2 Dashboard Views

**4.2.1 Executive Overview (default view)**
- **Signal counter cards:** Total signals this week, verified %, by signal type (with week-over-week change arrows)
- **BU activity heatmap:** Simple color-coded grid showing signal density per BU per week (last 12 weeks). Darker = more signals.
- **Top 5 signals this week:** Ranked by composite score with one-line summaries
- **AI Recommendations panel:** 2-3 proactive recommendations (see Section 5)
- **Competitive pulse:** Bar chart showing competitor mention frequency, last 4 weeks

**4.2.2 Intelligence Feed (real-time)**
- Chronological stream of all collected signals, newest first
- Filter sidebar: by BU, signal type, source channel, validation status, date range, company name
- Search: Full-text search across headlines, summaries, and source content
- Click any signal to expand into full Action Card view with all sources
- Bulk actions: Mark as "acted on", assign to team member (name/role text field), dismiss

**4.2.3 Trends View**
- Interactive line charts (use Recharts) showing Google Trends data per keyword over time
- Comparison mode: overlay multiple keywords on same chart
- Rising queries table with BU relevance mapping
- Geographic interest map (if feasible with simple chart library, otherwise table view)

**4.2.4 Competitor View**
- Per-competitor profile pages showing: all signals mentioning them, timeline of activity, signal type distribution
- "Competitor Strategy Alerts" when pattern detection triggers (see Section 5)
- Side-by-side comparison of competitor activity levels

**4.2.5 Reports View**
- Monthly effectiveness report (auto-generated)
- On-demand export: select date range + BUs + filters → generate PDF or HTML report
- Signal-to-action conversion tracking (based on feedback data)

### 4.3 Authentication

Keep it simple for V2:
- Basic password protection (single admin password stored as hashed value in .env)
- No user management system yet — all authenticated users see all data
- HTTPS required (use Let's Encrypt if hosted on VPS)

---

## 5. Proactive AI Recommendations Engine

### 5.1 Pattern Detection

Run analysis after each weekly collection cycle. Use Claude Sonnet to analyze the full signal database and generate recommendations.

**Recommendation Types:**

**Trend Alert** — When signals about a specific industry/technology increase >50% week-over-week for 2+ consecutive weeks:
> "🔥 Rising Activity: Humanoid robotics signals up 73% over 3 weeks across Force Sensors and Micro-Measurements. 4 new companies mentioned. Consider: create a robotics-focused application note and targeted outreach to Figure AI, Agility Robotics."

**Competitor Strategy Alert** — When a competitor appears in 3+ signals within 4 weeks with a common thread:
> "⚠️ Competitor Pattern: Kistler has made 4 moves in automotive crash testing in 3 weeks — new product announcement, two trade show presentations, and a partnership with a Tier 1 OEM. This appears to be a coordinated push into DTS's core market. Recommended: brief DTS sales team, update competitive battle card, consider defensive content strategy."

**Cross-BU Opportunity** — When a signal or company maps to 2+ BUs:
> "🤝 Cross-BU: Boeing's new materials testing facility expansion (identified via r/aerospace, confirmed by 3 trade sources) is relevant to Gleeble (materials simulation), Micro-Measurements (strain testing), and Pacific Instruments (DAQ). A combined VPG solution pitch could differentiate against single-product competitors."

**Persistent Signal** — When the same topic appears 3+ times across consecutive weeks:
> "📌 Persistent: 'India semiconductor manufacturing expansion' has appeared in 7 signals over 4 weeks. This is transitioning from news to a strategic opportunity. Consider: dedicated VPG Foil Resistors India strategy brief for the semiconductor fab market."

### 5.2 Recommendation Lifecycle

1. AI generates recommendation → stored in `ai_recommendations` table with status "new"
2. Appears in dashboard's Recommendations panel
3. User can: Acknowledge (status → "acknowledged"), Act On (status → "acted_on", records timestamp), or Dismiss (status → "dismissed")
4. Dismissed recommendations train the AI to reduce similar future recommendations
5. Monthly report shows: recommendations generated, acknowledged, acted upon

---

## 6. Implementation Plan

### Phase 2A: Database & Reddit (Weeks 1-3)

1. Design and implement new database schema (preserve V1 data via migration)
2. Build Reddit monitoring module with PRAW
3. Implement AI-powered relevance filtering for Reddit signals (confidence threshold 0.7)
4. Integrate Reddit signals into existing weekly digest pipeline
5. Add Reddit source configuration to existing Config UI
6. Test with 5 subreddits for 2 weeks, expand to full list after validation
7. Ensure V1 digest continues working throughout

### Phase 2B: Google Trends & Dashboard (Weeks 3-5)

1. Implement pytrends integration with keyword tracking per BU
2. Build weekly/monthly trends collection schedule
3. Add "Search Demand Radar" section to weekly email digest
4. Build executive dashboard (extend existing Config UI)
5. Implement Intelligence Feed with filtering and search
6. Build Trends visualization view
7. Add Competitor view with per-competitor profiles

### Phase 2C: AI Recommendations & Polish (Weeks 5-7)

1. Build pattern detection engine (runs post-collection)
2. Implement all 4 recommendation types
3. Build recommendation lifecycle tracking in dashboard
4. Add on-demand report generation (export to HTML/PDF)
5. Implement monthly effectiveness report auto-generation
6. End-to-end testing of full V2 pipeline
7. Performance optimization (dashboard load times, query efficiency)
8. Documentation update

---

## 7. API Endpoints (New for V2)

Add these to the existing V1 API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/signals | GET | List signals with filtering (bu, type, channel, date, company, search) |
| /api/signals/:id | GET | Full signal detail with sources, Reddit data, feedback |
| /api/signals/:id/feedback | POST | Submit thumbs up/down rating |
| /api/signals/:id/status | PUT | Mark as acted_on, dismissed, assigned |
| /api/signals/search | GET | Full-text search across all signal content |
| /api/signals/stats | GET | Aggregate statistics for dashboard cards |
| /api/competitors | GET | List competitors with signal counts and recent activity |
| /api/competitors/:name | GET | Competitor profile with all related signals |
| /api/trends | GET | Google Trends data with keyword/BU/date filtering |
| /api/trends/rising | GET | Rising queries with BU relevance mapping |
| /api/recommendations | GET | AI recommendations with status filtering |
| /api/recommendations/:id | PUT | Update recommendation status (acknowledge, act, dismiss) |
| /api/reports/monthly | GET | Generate monthly effectiveness report |
| /api/reports/custom | POST | Generate custom report with date range and filters |
| /api/reddit/subreddits | GET/POST/DELETE | Manage monitored subreddits |
| /api/reddit/health | GET | Reddit source health and collection stats |

---

## 8. Critical Rules for V2

1. **V1 must keep working.** The weekly email digest, source validation, Gmail delivery — everything from V1 continues unchanged. V2 is additive.
2. **Reddit signals are second-class citizens** until corroborated. Always display with informal source indicator. Never let a Reddit-only signal score above 7.0 without traditional source corroboration.
3. **Google Trends data is directional, not absolute.** Always present as "interest trending up/down" — never as "demand is X units." Label all Trends data clearly.
4. **Database queries must be fast.** Dashboard should load in <2 seconds. Use proper indexes on all filtered columns (bu_code, signal_type, created_at, company_name, validation_status).
5. **AI recommendation costs matter.** Batch signals for analysis. Don't make individual API calls per signal for pattern detection — send the full week's signals in one structured prompt.
6. **Reddit rate limiting is real.** PRAW handles it, but implement additional safeguards: max 50 requests per collection run per subreddit, with exponential backoff on 429 errors.
7. **pytrends gets blocked easily.** Implement delays (2-5 seconds between requests), rotate through a small set of proxy addresses if needed, and cache aggressively — only pull data that's actually new.
8. **Keep the dashboard simple.** Executive users want answers, not dashboards to explore. Default views should answer the question "what should I pay attention to?" without any clicks.

---

## 9. Environment Variables (New for V2)

Add to `.env`:

```
# Reddit API
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT=vpg-intelligence:v2.0 (by /u/YOUR_USERNAME)

# Google Trends
GOOGLE_TRENDS_MODE=pytrends  # or 'official_api' when approved
GOOGLE_TRENDS_API_KEY=       # Only if using official API

# Dashboard
DASHBOARD_PASSWORD_HASH=     # bcrypt hash of admin password
DASHBOARD_PORT=3000
DASHBOARD_SECRET=             # Session secret for auth cookies
```

Add all of these to `.env.example` with placeholder values and to `.gitignore`.

---

## 10. Testing Checklist for V2

- [ ] V1 weekly digest still generates and sends correctly
- [ ] Reddit collection returns relevant signals from at least 5 subreddits
- [ ] Reddit relevance filtering correctly excludes >80% of raw posts as irrelevant
- [ ] Google Trends data populates for all configured keywords
- [ ] Database migration preserves all V1 historical data
- [ ] Dashboard loads in <2 seconds with 1000+ signals in database
- [ ] Intelligence Feed search returns results in <1 second
- [ ] Competitor view correctly aggregates signals per competitor
- [ ] AI recommendations generate after weekly collection
- [ ] Recommendation status updates persist correctly
- [ ] Monthly report generates with accurate statistics
- [ ] All new API endpoints return correct data with proper error handling
- [ ] Reddit credentials are not committed to git
- [ ] pytrends respects rate limits and doesn't get blocked during full scan
