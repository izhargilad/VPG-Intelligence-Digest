# VPG Weekly Intelligence Digest — Automated Agent
## Technical Build Brief for Claude Code

**Prepared by:** Strategic Initiatives  
**Date:** February 16, 2026  
**Version:** 1.0

> **CORE OBJECTIVE:** Build an intelligent agent that transforms raw industry signals into actionable business intelligence for VPG's 9 business units. Every signal must link to a specific action, owner, and revenue opportunity. This is not a news aggregator — it is a competitive weapon that drives weekly pipeline activity.

> **BUILD NOTE:** Build the delivery module with a mock/file-output mode first. Gmail API credentials will be provided separately. Generate digests as local HTML files for preview until email delivery is connected.

---

## 1. Project Overview

### 1.1 What This Agent Must Deliver

Every Monday morning, each recipient receives an email containing a fully researched, source-validated intelligence digest. The digest is not a summary of news — it is a prioritized set of business actions, each backed by at least 3 validated sources, each tied to a specific VPG business unit, and each with a clear next step that can be executed that same week.

### 1.2 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Delivery reliability | 100% on-time (Monday 7 AM ET) | Automated monitoring |
| Source validation | 3+ sources per signal, all cited | Audit trail in digest |
| Action specificity | Named BU + contact + next step | Weekly review |
| Inbox delivery rate | >95% (not spam-filtered) | Delivery tracking |
| Time-to-action | <24 hours from receipt | Team feedback |
| Signal relevance | >80% rated useful by recipients | Monthly survey |

---

## 2. System Architecture

### 2.1 High-Level Architecture

The agent operates as a modular pipeline with 6 stages. Each stage is independently testable and can be re-run if failures occur. The system uses a configuration-driven approach where all business units, industries, recipients, and source priorities are stored in editable JSON/YAML configuration files with a simple web UI overlay.

| Stage | Component | Description |
|-------|-----------|-------------|
| 1 | Configuration Manager | Web UI for managing BUs, industries, recipients, sources. Stores in config files. |
| 2 | Intelligence Collector | Multi-source web scraping, RSS, API ingestion. Runs Saturday-Sunday. |
| 3 | Validation Engine | Cross-references each signal against 3+ independent sources. Flags unverified. |
| 4 | Analysis & Scoring | AI-powered relevance scoring, BU matching, action generation, impact estimation. |
| 5 | Digest Composer | Generates responsive HTML email with images, links, structured sections per BU. |
| 6 | Distribution Engine | Gmail API delivery with recipient management, tracking, retry logic. |

### 2.2 Technology Stack (Recommended)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Runtime | Node.js / Python | Claude Code native support; Python preferred for scraping/NLP |
| Web UI (Config) | React + Tailwind (single page) | Lightweight config management, no backend framework needed |
| Data Storage | SQLite + JSON config files | Zero infrastructure; portable; easy backup |
| Email Delivery | Gmail API (OAuth2) | No SMTP relay issues; high deliverability; free tier sufficient |
| Web Scraping | Playwright + Cheerio | Handles JS-rendered pages; lightweight for static content |
| RSS/Feed Parsing | feedparser (Python) | Mature, handles edge cases well |
| AI Analysis | Anthropic API (Claude Sonnet) | Cost-effective for scoring and action generation at scale |
| Scheduling | Cron (Linux) or node-cron | Simple, reliable, no external scheduler dependency |
| Image Handling | Sharp (Node.js) | Resize/optimize source images for email embedding |
| Hosting | Local machine / VPS / Docker | Self-contained; can run on any Linux environment |

---

## 3. Configuration Management (Web UI)

> **KEY REQUIREMENT: No-Code Configuration**  
> All configuration changes — adding industries, managing recipients, adjusting BU settings — must be possible through the web UI without editing any code or config files directly. The UI should be intuitive enough for any team member.

### 3.1 Configuration UI Requirements

**Tab 1: Business Units & Industries**
- Display all 9 BUs with their current industry coverage
- Each BU shows: Name, assigned industries, key competitors, priority sources
- **"Add Industry" button:** Opens form with fields for: Industry name, relevant BUs (multi-select), priority keywords, key companies to monitor, preferred source types
- **"Edit Industry"** allows modifying keywords, BU associations, and source priorities
- Drag-and-drop priority ordering for industries within each BU

**Tab 2: Recipients Management**
- Table view: Name, Email, Role, BU Filter (which BUs they receive), Status (active/paused)
- **"Add Recipient" button:** Name, email, role, BU interest filter (can select All or specific BUs)
- Toggle active/inactive without deleting (for vacations, role changes)
- "Send Test Digest" button per recipient for verification
- Recipient groups (e.g., "Executive Team", "Sales Team", "Marketing") for batch management

**Tab 3: Sources & Monitoring**
- Source health dashboard: Last successful scrape, error count, reliability score
- Add custom RSS feeds, websites, or API endpoints
- Source priority tiers: Tier 1 (industry authorities), Tier 2 (news), Tier 3 (social/forums)
- Blacklist management for unreliable or irrelevant sources

**Tab 4: Digest Preview & History**
- Preview next digest before sending (with manual override/edit capability)
- Archive of all past digests with search
- Analytics: open rates (if Gmail API supports), click-through on links

### 3.2 VPG Business Unit Configuration

Pre-configure these 9 BUs with their full industry and keyword mappings:

| Business Unit | Core Industries | Key Monitoring Keywords |
|--------------|----------------|----------------------|
| VPG Force Sensors | Robotics, automation, aerospace, medical devices, industrial weighing | load cell, force transducer, torque sensor, humanoid robot, cobot |
| VPG Foil Resistors | Aerospace/defense, semiconductor test, precision instrumentation | foil resistor, current sense, Z1-Foil, precision measurement, mil-spec |
| Micro-Measurements | Structural testing, aerospace, automotive R&D, civil engineering | strain gage, stress analysis, experimental mechanics, SHM |
| VPG Onboard Weighing | Heavy vehicles, mining, logistics, waste management | onboard weighing, payload monitoring, VanWeigh, fleet compliance |
| BLH Nobel | Process industries, steel, chemicals, food & beverage | process weighing, KIS load cell, industrial automation, batch weighing |
| KELK | Steel mills, aluminum rolling, metals processing | rolling mill, thickness measurement, Nokra, laser gauge, alpha.ti |
| Gleeble | Materials research, metals R&D, university labs, foundries | thermal-mechanical simulation, Gleeble, materials testing, metallurgy |
| Pacific Instruments | Aerospace testing, defense, nuclear, extreme environments | data acquisition, high-channel DAQ, signal conditioning |
| DTS | Automotive crash test, defense ballistics, biomechanics | miniature DAQ, crash test, accelerometer, data recorder |

---

## 4. Intelligence Collection Engine

### 4.1 Source Categories & Priorities

| Tier | Source Type | Examples | Frequency |
|------|-----------|----------|-----------|
| 1 | Industry Authorities | AIST, SAE, IEEE, ASTM, NIST publications | Daily RSS/API check |
| 1 | Company Filings & PR | SEC filings, press releases, investor calls | Daily |
| 1 | Government/Regulatory | NHTSA, DOD contracts, trade regulations | Daily |
| 2 | Industry News | MetalMiner, Robotics Business Review, EE Times | Daily RSS |
| 2 | Trade Publications | Assembly Magazine, Quality Magazine, Sensors Magazine | Daily RSS |
| 2 | Competitor Monitoring | TT Electronics, HBK, Zemic, Kistler websites/news | 2x weekly |
| 3 | LinkedIn & Social | Industry influencer posts, company updates | 3x weekly |
| 3 | Patent Filings | USPTO, EPO for relevant technology patents | Weekly |
| 3 | Job Postings | Competitor/customer hiring signals on LinkedIn/Indeed | Weekly |

### 4.2 Signal Detection Categories

The agent must classify every collected signal into one of these categories, which determine the action template used:

| Signal Type | Description | Action Template |
|------------|-------------|-----------------|
| ⚠ Competitive Threat | Competitor product launch, acquisition, price change, patent | Defensive positioning brief + talking points |
| 💰 Revenue Opportunity | Customer expansion, new facility, RFP, budget cycle | Prospect brief + suggested outreach approach |
| 🎯 Market Shift | Regulation change, technology trend, supply chain disruption | Impact assessment + BU response recommendation |
| 🤝 Partnership Signal | OEM announcements, integration opportunities, distributor moves | Partnership evaluation + contact suggestion |
| 📊 Customer Intelligence | Existing customer news (expansion, challenges, leadership change) | Account review trigger + talking points |
| 🚀 Technology Trend | Emerging tech relevant to VPG capabilities | Capability mapping + whitepaper/content opportunity |
| 🌍 Trade & Tariff | US-China trade updates, tariff changes, reshoring trends | Supply chain impact + India production advantage talking points |

### 4.3 Source Validation Protocol

> **MANDATORY: 3-Source Validation Rule**  
> Every signal included in the digest MUST be corroborated by at least 3 independent sources. The validation engine must cross-reference and flag any signal that cannot meet this threshold as "Unverified" with a clear visual indicator in the digest. Sources must be from different publishers.

**Validation workflow:**
1. Primary signal detected from any source
2. Agent searches for corroborating evidence from at least 2 additional independent sources
3. If 3+ sources confirm: Signal marked **VERIFIED** with all source links
4. If 2 sources only: Signal marked **LIKELY** with caveat note
5. If 1 source only: Signal flagged **UNVERIFIED** — included only if high-impact, with clear warning
6. Conflicting sources: Signal includes both perspectives with analysis

---

## 5. AI Analysis & Action Generation

### 5.1 Signal Scoring Matrix

Each validated signal is scored on 4 dimensions using the Anthropic API (Claude Sonnet). The composite score determines digest placement priority:

| Dimension | Weight | Scoring Criteria (1-10) |
|-----------|--------|------------------------|
| Revenue Impact | 35% | Direct revenue opportunity size estimate. 10 = >$1M, 7 = $500K-$1M, 4 = $100K-$500K, 1 = <$100K |
| Time Sensitivity | 25% | How quickly action is needed. 10 = this week, 7 = this month, 4 = this quarter, 1 = 6+ months |
| Strategic Alignment | 25% | Alignment with VPG priorities (current initiatives, target accounts, key verticals) |
| Competitive Pressure | 15% | Does a competitor gain advantage if VPG doesn't act? 10 = immediate threat |

### 5.2 Action Card Format

Every signal in the digest must be presented as a structured Action Card:

```
┌──────────────────────────────────────────────────────────┐
│ [SIGNAL TYPE ICON]  HEADLINE                [SCORE: 8.5] │
│ BU: VPG Force Sensors | Industry: Robotics               │
│──────────────────────────────────────────────────────────│
│ WHAT: 2-3 sentence summary of the signal                 │
│ WHY IT MATTERS: Specific relevance to this BU            │
│ QUICK WIN: Concrete action to take THIS WEEK             │
│ OWNER: Suggested role/person to take action              │
│ EST. IMPACT: Revenue/pipeline estimate                   │
│ SOURCES: [Link 1] | [Link 2] | [Link 3]                │
└──────────────────────────────────────────────────────────┘
```

---

## 6. Email Digest Design & Delivery

### 6.1 Email Structure

Dynamic structure based on the week's signals:

1. **Header:** VPG logo + "Weekly Intelligence Digest" + Date range + Issue number
2. **Executive Summary:** 3-5 bullet "Top Signals This Week" with scores and BU tags (acts as TL;DR)
3. **Signal-of-the-Week Spotlight:** The #1 highest-scored signal gets expanded treatment with background image from source
4. **BU Sections:** Each BU with signals gets its own section with Action Cards. BUs with no signals are omitted (not shown as empty)
5. **Cross-BU Opportunities:** Signals relevant to multiple BUs highlighted with collaboration suggestions
6. **Competitive Radar:** Visual summary of competitor activity (simple table, not complex graphics)
7. **Trade & Tariff Watch:** US-China/India production angle updates
8. **Upcoming Events & Deadlines:** Relevant industry events, RFP deadlines, conference prep windows
9. **Quick Stats:** Key numbers from the week (e.g., steel price movements, robotics investment figures)
10. **Footer:** Unsubscribe link, feedback link, archive link, "Powered by VPG Strategic Intelligence"

### 6.2 Email Design Specifications

| Specification | Requirement |
|--------------|-------------|
| Max width | 600px (email standard for cross-client rendering) |
| Responsive | Must stack to single column on mobile (<480px) |
| Images | Real images from sources only, no AI-generated. Inline via CID or base64. Max 600px wide, <100KB each, with alt text |
| Font stack | Arial, Helvetica, sans-serif (web-safe only for email) |
| Color scheme | VPG brand colors: Navy (#1B2A4A), Blue (#2E75B6), Accent (#E8792F) |
| CTA buttons | High-contrast buttons for key actions ("View Full Report", "Contact Account Manager") |
| Spam prevention | No excessive images, no ALL CAPS subjects, text-to-image ratio >60:40, valid DKIM/SPF via Gmail |
| Subject line format | "VPG Intel [Week #]: [Top Signal Headline] + [X] more signals" |
| Preheader text | Dynamic summary of top 3 signal headlines |
| Link handling | All source links open in new tab; UTM parameters for internal links |

### 6.3 Gmail Delivery Configuration

Use the Gmail API with OAuth2 for reliable delivery. This avoids SMTP relay issues and ensures messages come from a real Gmail account, maximizing deliverability.

**Setup requirements:**
- Google Cloud Console project with Gmail API enabled
- OAuth2 credentials (client ID + secret) stored securely in environment variables
- One-time authorization flow to generate refresh token
- Sender address: configurable (e.g., vpg.intelligence@gmail.com or personal Gmail)
- Rate limiting: max 100 emails/day (well within Gmail limits)
- Retry logic: 3 retries with exponential backoff on send failures
- Delivery logging: record send status, timestamp, and any errors per recipient

**Alternative delivery option:** If Gmail API proves insufficient for volume or deliverability, the architecture should allow easy swap to SendGrid, Postmark, or Amazon SES by implementing a delivery provider interface pattern. The email composition layer should be completely decoupled from the delivery layer.

---

## 7. Enhanced Features & Proactive Additions

Beyond the core requirements, these features transform the digest from an information product into a competitive intelligence platform:

### 7.1 Trend Tracking & Pattern Detection

**Rolling Signal Heatmap:** Track signal density per BU per week. After 4+ weeks, the agent can identify rising and declining trends. Include a simple "Trending Up / Trending Down" indicator per industry in each digest.

**Recurring Theme Alerts:** If the same company, technology, or regulation appears 3+ times across consecutive digests, flag it as a "Persistent Signal" requiring strategic attention rather than tactical response.

**Competitor Movement Tracker:** Maintain a rolling log of competitor activities. When a competitor makes 2+ moves in the same area within 4 weeks, generate a "Competitor Strategy Alert" with analysis of what they may be building toward.

### 7.2 Proactive Opportunity Matching

**Customer Expansion Triggers:** When a known VPG customer announces facility expansion, new product launch, or hiring surge, automatically generate an upsell/cross-sell brief with specific products from relevant BUs.

**"Did You Know?" Cross-BU Connections:** When a signal is relevant to 2+ BUs, generate a brief showing how combined VPG solutions could create a differentiated value proposition that no single competitor can match.

**Pre-Event Intelligence Packs:** Before major industry events (AISTech, IMTS, Sensors Expo), automatically compile intelligence on confirmed exhibitors, announced products, and potential meeting targets specific to VPG's presence.

### 7.3 Actionability Accelerators

**One-Click Outreach Templates:** For "Revenue Opportunity" signals, generate a suggested email/LinkedIn outreach message that the salesperson can personalize and send. Link directly from the digest to a pre-drafted message.

**Competitive Battle Cards (Auto-Updated):** When competitor intelligence is detected, automatically update a running competitive positioning document. Include a link in the digest to the latest version.

**ROI Quick-Calc Links:** For signals where VPG can demonstrate quantifiable value (e.g., KELK TCO savings vs. X-ray), auto-link to the relevant ROI calculator or TCO comparison tool.

**Meeting Prep Briefs:** When signals mention strategic target accounts (Caterpillar, Humanetics, Saronic, etc.), auto-generate a 1-page account intelligence brief that a salesperson can review before any call.

### 7.4 Feedback Loop & Learning

**Signal Rating System:** Each action card in the email includes a simple thumbs-up/thumbs-down link. Clicks feed back into the scoring algorithm to improve relevance over time.

**Monthly Effectiveness Report:** Auto-generate a monthly summary showing: signals delivered, actions taken (based on feedback), estimated pipeline influenced, and accuracy trends.

**Self-Improving Keyword Expansion:** When recipients consistently rate signals from a particular keyword or source highly, the agent automatically expands monitoring in that area. Conversely, consistently low-rated areas get deprioritized.

### 7.5 India Production Advantage Monitor

Given VPG's main production hub in India, the agent should actively monitor:
- US-China tariff updates and how they create competitive advantage for India-manufactured products
- India manufacturing policy changes (PLI schemes, duty structures, trade agreements)
- Competitor supply chain vulnerabilities from China dependency
- Customer reshoring/nearshoring announcements that align with VPG's India production capability

Each relevant trade signal should include a specific talking point about VPG's India production advantage for sales enablement.

### 7.6 Executive Dashboard (Optional Phase 2)

If the web UI proves valuable, extend it with a live dashboard:
- Real-time signal feed with filtering by BU, industry, signal type
- Interactive trend charts showing signal density over time
- Pipeline tracking: link signals to actual deals closed (manual input)
- ROI calculator: show estimated value of intelligence delivered
- Export: generate on-demand intelligence reports for specific accounts or industries

---

## 8. Implementation Plan

### 8.1 Phased Build Approach

**PHASE 1: Foundation (Weeks 1-3)**  
Core infrastructure and first working digest delivery.

1. Set up project structure, SQLite database schema, and JSON config files
2. Build Configuration Web UI with BU management, recipient management, and industry management tabs
3. Implement RSS feed parser and basic web scraper (Tier 1 sources only)
4. Build 3-source validation engine with source cross-referencing logic
5. Create Gmail API integration with OAuth2 flow and send capability
6. Build basic HTML email template (responsive, VPG-branded)
7. Deliver first manual test digest to validate end-to-end pipeline

**PHASE 2: Intelligence (Weeks 4-6)**  
AI-powered analysis and action generation.

1. Integrate Anthropic API for signal scoring and action card generation
2. Implement signal type classification and BU matching logic
3. Build Action Card HTML template with all required fields
4. Add Tier 2 and Tier 3 source monitoring
5. Implement competitor monitoring module
6. Add image extraction and embedding from source articles
7. Build automated weekly scheduling (cron)
8. 4-week pilot with core team for feedback collection

**PHASE 3: Enhancement (Weeks 7-10)**  
Advanced features and optimization based on pilot feedback.

1. Implement trend tracking and pattern detection
2. Build feedback loop (thumbs-up/down) and scoring algorithm refinement
3. Add cross-BU opportunity matching
4. Implement pre-event intelligence packs
5. Build one-click outreach template generation
6. Add India production advantage monitoring module
7. Monthly effectiveness report generation
8. Documentation and handoff procedures

---

## 9. Technical Specifications

### 9.1 Project File Structure

```
/vpg-intelligence/
├── config/
│   ├── business-units.json       # BU definitions, industries, keywords, competitors
│   ├── sources.json              # RSS feeds, websites, API endpoints per tier
│   ├── recipients.json           # Email recipients with BU filters and groups
│   └── scoring-weights.json      # Signal scoring dimension weights
├── src/
│   ├── collector/                # Web scraping, RSS parsing, API ingestion modules
│   ├── validator/                # 3-source validation engine
│   ├── analyzer/                 # AI scoring, classification, action generation
│   ├── composer/                 # HTML email template engine
│   ├── delivery/                 # Gmail API integration, retry logic, logging
│   └── ui/                       # React configuration web app
├── templates/                    # HTML email templates (base, action-card, section)
├── data/                         # SQLite database, signal archive, image cache
├── logs/                         # Execution logs, delivery logs, error logs
├── tests/                        # Unit and integration tests
├── docker-compose.yml            # Containerized deployment
├── .env.example                  # Environment variable template
└── README.md                     # Setup and usage documentation
```

### 9.2 Key API Contracts

The following REST API endpoints power the configuration UI:

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/business-units | GET/PUT | List and update BU configurations |
| /api/industries | GET/POST/DELETE | Manage industry definitions and BU associations |
| /api/recipients | GET/POST/PUT/DELETE | Full CRUD for recipient management |
| /api/recipients/:id/test | POST | Send test digest to specific recipient |
| /api/sources | GET/POST/PUT/DELETE | Manage monitored sources |
| /api/sources/health | GET | Source health dashboard data |
| /api/digest/preview | GET | Preview next digest content |
| /api/digest/send | POST | Manually trigger digest send |
| /api/digest/history | GET | List past digests with search |
| /api/feedback | POST | Signal rating feedback endpoint (from email links) |
| /api/analytics | GET | Delivery and engagement analytics |

### 9.3 Anthropic API Integration Pattern

Use the following prompt engineering approach for the AI analysis layer:
- **System prompt:** Define VPG's BU structure, product portfolio, strategic priorities, and target accounts as persistent context
- **Signal prompt:** Pass the validated signal text + metadata, request structured JSON output with: signal_type, relevant_bus (array), score_dimensions (4 scores), headline, summary, why_it_matters, quick_win_action, suggested_owner_role, estimated_impact_range, outreach_template (optional)
- **Model:** Use Claude Sonnet for cost efficiency at scale (potentially 50-200 signals/week)
- **Temperature:** 0.3 for consistent, factual analysis
- **Batch processing:** Group signals by BU for context efficiency

---

## 10. Critical Requirements & Guardrails

> **NON-NEGOTIABLE REQUIREMENTS:**
> 1. Every signal must cite 3+ validated sources with clickable links
> 2. Every signal must map to at least one VPG BU
> 3. Every signal must include a specific, executable action
> 4. Email must render correctly on Gmail, Outlook, Apple Mail, and mobile
> 5. No AI-generated images — only real images from source articles
> 6. All configuration changes via UI — no code edits for operational changes
> 7. System must gracefully handle source failures without blocking digest
> 8. Recipient data must be stored securely; unsubscribe must work immediately
> 9. The digest must be scannable in <3 minutes by a busy executive
> 10. Archive all digests and enable search across historical intelligence

### 10.1 Error Handling Requirements

| Failure Scenario | Handling |
|-----------------|----------|
| Source unreachable | Skip source, log error, continue. Alert if Tier 1 source fails 3x consecutively. |
| <3 sources for validation | Mark signal as UNVERIFIED. Include only if score >8.0 with prominent warning label. |
| AI analysis fails | Retry 3x. If still failing, include raw signal with minimal formatting and manual review flag. |
| Gmail API failure | Retry with exponential backoff (3 attempts). If final failure, send admin alert email via backup SMTP. |
| No signals found for a BU | Omit BU section entirely. Note in executive summary that no new signals were detected for that BU. |
| All sources fail | Send minimal digest with error report. Do NOT send empty digest. |
| Image extraction fails | Use BU-specific placeholder icon. Never use AI-generated fallback images. |

---

## 11. Testing & Quality Assurance

### 11.1 Test Strategy

| Test Type | Scope | Automation |
|-----------|-------|------------|
| Unit Tests | Individual modules (scraper, validator, scorer, composer) | Automated, run on every code change |
| Integration Tests | End-to-end pipeline from collection to email generation | Automated, run weekly |
| Email Rendering | Cross-client testing (Gmail, Outlook, Apple Mail, mobile) | Manual first month, then Litmus/Email on Acid |
| Deliverability | Spam filter testing across major email providers | Manual using mail-tester.com |
| Load Testing | Process 500+ signals in single run without degradation | Automated stress test |
| Config UI Tests | All CRUD operations, edge cases, concurrent users | Automated E2E with Playwright |

### 11.2 Acceptance Criteria for V1 Release

- Successfully deliver 4 consecutive weekly digests to pilot group without manual intervention
- All 9 BUs represented in configuration with relevant source monitoring active
- Recipient management fully functional via web UI (add, remove, pause, test)
- Industry management fully functional via web UI (add, modify, assign to BUs)
- >90% of signals include 3+ validated sources
- Email renders correctly on Gmail web, Gmail mobile, Outlook desktop, and Apple Mail
- Average digest generation time <30 minutes from start to send-ready
- Feedback mechanism (thumbs up/down) functional and data captured

---

## 12. Summary & Next Steps

This brief defines a production-ready intelligence agent that will deliver measurable competitive advantage to VPG's go-to-market teams. The phased approach ensures early value delivery while building toward a comprehensive intelligence platform.

**Immediate next steps:**
1. Review this brief and confirm scope / priorities
2. Set up Google Cloud project and Gmail API credentials
3. Create Anthropic API key for the analysis engine
4. Define initial pilot recipient list (5-10 people)
5. Begin Phase 1 build with Claude Code

> **THE BOTTOM LINE:** This agent turns VPG's competitive intelligence from a passive "nice to know" into an active "must act" system. Every signal is a potential deal. Every digest is a pipeline accelerator. The goal is simple: by the time a competitor spots an opportunity, VPG's team has already made the call.
