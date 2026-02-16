# VPG Weekly Intelligence Digest Agent

> Full specification: see `BRIEF.md` in this repo. Read it before starting any new phase.

## What This Is

An automated agent that scans industry sources weekly, validates signals against 3+ sources, scores them by business impact, and delivers a formatted HTML email digest with actionable intelligence to VPG's sales, marketing, and executive teams.

## Architecture (6-Stage Pipeline)

```
Collection → Validation → AI Analysis → Scoring → Email Composition → Delivery
(Sat-Sun)    (3+ sources)  (Anthropic)   (4-dim)   (responsive HTML)   (Gmail API)
```

## Tech Stack

- **Runtime:** Python (preferred) + Node.js where needed
- **Config UI:** React + Tailwind (single-page app)
- **Storage:** SQLite + JSON config files
- **Email:** Gmail API (OAuth2) — build with mock/file-output mode first
- **Scraping:** Playwright + Cheerio (or BeautifulSoup for Python)
- **AI:** Anthropic API (Claude Sonnet, temperature 0.3)
- **Scheduling:** cron or node-cron
- **Images:** Sharp for resize/optimize

## The 9 Business Units

| BU | Key Products | Core Industries |
|----|-------------|----------------|
| VPG Force Sensors | Load cells, force transducers, torque sensors | Robotics, automation, aerospace, medical |
| VPG Foil Resistors | Z1-Foil precision resistors, current sensing | Aerospace/defense, semiconductor test |
| Micro-Measurements | Strain gages, stress analysis systems | Structural testing, automotive R&D |
| VPG Onboard Weighing | VanWeigh, TruckWeigh, BulkWeigh | Heavy vehicles, mining, logistics |
| BLH Nobel | KIS load cells, process weighing | Steel, chemicals, food & beverage |
| KELK | Rolling mill systems, Nokra laser measurement | Steel mills, aluminum, metals processing |
| Gleeble | Thermal-mechanical simulation systems | Materials research, university labs |
| Pacific Instruments | High-performance DAQ systems | Aerospace testing, defense, nuclear |
| DTS | Miniature data acquisition, crash test sensors | Automotive crash test, ballistics |

## Signal Types & Action Templates

- **⚠ Competitive Threat** → Defensive positioning brief + talking points
- **💰 Revenue Opportunity** → Prospect brief + outreach approach
- **🎯 Market Shift** → Impact assessment + BU response
- **🤝 Partnership Signal** → Partnership evaluation + contact
- **📊 Customer Intelligence** → Account review trigger + talking points
- **🚀 Technology Trend** → Capability mapping + content opportunity
- **🌍 Trade & Tariff** → Supply chain impact + India production advantage

## Scoring Matrix (determines digest placement priority)

| Dimension | Weight |
|-----------|--------|
| Revenue Impact | 35% |
| Time Sensitivity | 25% |
| Strategic Alignment | 25% |
| Competitive Pressure | 15% |

## Project Structure

```
/vpg-intelligence/
├── config/                  # JSON config files (BUs, sources, recipients, scoring)
├── src/
│   ├── collector/           # Web scraping, RSS, API ingestion
│   ├── validator/           # 3-source cross-referencing
│   ├── analyzer/            # Anthropic API scoring + action generation
│   ├── composer/            # HTML email template engine
│   ├── delivery/            # Gmail API + retry logic (mock mode available)
│   └── ui/                  # React config web app
├── templates/               # HTML email templates
├── data/                    # SQLite DB, signal archive, image cache
├── logs/                    # All execution and delivery logs
└── tests/                   # Unit + integration tests
```

## Non-Negotiable Rules

1. **3+ validated sources per signal** — cross-referenced from different publishers
2. **Every signal maps to a BU** — no orphan signals
3. **Every signal has a concrete action** — with owner role and next step
4. **No AI-generated images** — only real images from source articles
5. **All config via UI** — no code edits for operational changes
6. **Graceful failure** — source failures don't block the digest
7. **Scannable in <3 minutes** — executives won't read a novel

## Action Card Format (core deliverable unit)

Each signal becomes an Action Card with: Signal Type Icon, Headline, Score, BU tag, Industry tag, WHAT (2-3 sentence summary), WHY IT MATTERS (BU relevance), QUICK WIN (action for this week), OWNER (role), EST. IMPACT (revenue range), SOURCES (3+ clickable links).

## Email Specs

- 600px max width, mobile-responsive
- VPG colors: Navy #1B2A4A, Blue #2E75B6, Accent #E8792F
- Arial/Helvetica font stack
- Subject: "VPG Intel [Week #]: [Top Signal] + [X] more signals"
- Text-to-image ratio >60:40 (spam prevention)
- Dynamic structure: BUs with no signals are omitted, not shown empty

## Key Competitors to Monitor

TT Electronics, HBK (Hottinger Brüel & Kjær), Zemic, Rice Lake, Kistler, Kyowa, NMB, Omega, Novanta, Flintec, Sunrise Instruments, Figure AI, Boston Dynamics

## Strategic Context

- Main production hub: India (competitive advantage vs China-dependent competitors)
- Key target accounts: Caterpillar, Humanetics, Saronic Technologies
- Current initiative: KELK-Nokra alpha.ti laser thickness measurement (AISTech 2026 launch)
- US-China trade dynamics are a constant monitoring priority

## Build Phases

- **Phase 1 (Weeks 1-3):** Project structure, config UI, RSS/scraping, validation engine, Gmail integration (mock mode), basic HTML template, first test digest
- **Phase 2 (Weeks 4-6):** Anthropic API integration, scoring, action cards, Tier 2/3 sources, competitor monitoring, image embedding, cron scheduling, pilot
- **Phase 3 (Weeks 7-10):** Trend tracking, feedback loop, cross-BU matching, pre-event intel packs, outreach templates, India monitor, monthly reports

## Error Handling

- Source down → skip, log, continue (alert after 3x Tier 1 failure)
- <3 sources → mark UNVERIFIED (include only if score >8.0)
- AI failure → retry 3x, then include raw signal with manual review flag
- Gmail failure → retry 3x with backoff, then admin alert via backup
- No signals for BU → omit section, note in executive summary
- Image failure → BU-specific placeholder icon (never AI-generated)
