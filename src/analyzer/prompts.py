"""Prompt templates for Anthropic API signal analysis.

Contains the system prompt (VPG context) and signal analysis prompt builder.
"""

from src.config import get_business_units, get_scoring_weights

# Valid signal type IDs for classification
VALID_SIGNAL_TYPES = [
    "competitive-threat",
    "revenue-opportunity",
    "market-shift",
    "partnership-signal",
    "customer-intelligence",
    "technology-trend",
    "trade-tariff",
]


def build_system_prompt() -> str:
    """Build the system prompt with VPG's full strategic context.

    This provides the AI with persistent knowledge about VPG's business units,
    products, competitors, and strategic priorities.
    """
    bu_config = get_business_units()
    bus = bu_config.get("business_units", [])
    strategic = bu_config.get("strategic_context", {})

    bu_lines = []
    for bu in bus:
        products = ", ".join(bu.get("key_products", []))
        industries = ", ".join(bu.get("core_industries", []))
        competitors = ", ".join(bu.get("key_competitors", []))
        bu_lines.append(
            f"- **{bu['name']}** (id: {bu['id']}): "
            f"Products: {products}. "
            f"Industries: {industries}. "
            f"Competitors: {competitors or 'N/A'}."
        )
    bu_block = "\n".join(bu_lines)

    target_accounts = ", ".join(strategic.get("target_accounts", []))
    priorities = "\n".join(f"- {p}" for p in strategic.get("monitoring_priorities", []))

    initiatives = ""
    for init in strategic.get("current_initiatives", []):
        initiatives += f"- {init['name']}: {init['description']} (launch: {init.get('launch_event', 'TBD')})\n"

    return f"""You are VPG's Strategic Intelligence Analyst. Your job is to analyze industry signals and generate actionable intelligence for VPG's business teams.

## VPG Business Units

{bu_block}

## Strategic Context

- **Production Hub:** {strategic.get('production_hub', 'India')} — {strategic.get('india_advantage', 'competitive advantage vs China-dependent competitors')}
- **Target Accounts:** {target_accounts}
- **Current Initiatives:**
{initiatives}
## Monitoring Priorities

{priorities}

## Key Competitors Across All BUs

TT Electronics, HBK (Hottinger Bruel & Kjaer), Zemic, Rice Lake, Kistler, Kyowa, NMB, Omega, Novanta, Flintec, Sunrise Instruments, Figure AI, Boston Dynamics

## Your Analysis Requirements

1. Every signal MUST map to at least one VPG business unit
2. Every signal MUST include a specific, executable action for this week
3. Scoring must be objective and evidence-based
4. Actions must name a specific owner role (e.g., "VP Sales - Force Sensors", "BU Manager - KELK")
5. Revenue impact estimates must be realistic and grounded
6. When trade/tariff signals arise, always include VPG's India production advantage angle"""


def build_signal_prompt(signal: dict) -> str:
    """Build the analysis prompt for a single signal.

    Args:
        signal: Signal dict with title, summary, url, source info, etc.

    Returns:
        User prompt string requesting structured JSON analysis.
    """
    scoring = get_scoring_weights()
    dims = scoring["scoring_dimensions"]
    dim_descriptions = []
    for dim_id, dim_config in dims.items():
        scale_items = dim_config.get("scale", {})
        scale_str = "; ".join(f"{k}={v}" for k, v in sorted(scale_items.items(), key=lambda x: int(x[0]), reverse=True))
        dim_descriptions.append(
            f"- **{dim_config['label']}** (weight: {dim_config['weight']}, id: {dim_id}): "
            f"{dim_config['description']}. Scale: {scale_str}"
        )
    scoring_block = "\n".join(dim_descriptions)

    signal_types = ", ".join(f'"{t}"' for t in VALID_SIGNAL_TYPES)

    return f"""Analyze this industry signal and produce a structured intelligence assessment.

## Signal Data

**Title:** {signal.get('title', 'N/A')}
**Source:** {signal.get('source_name', 'Unknown')} (Tier {signal.get('source_tier', '?')})
**URL:** {signal.get('url', 'N/A')}
**Published:** {signal.get('published_at', 'Unknown')}
**Summary:** {signal.get('summary', 'No summary available')}
**Full Content:** {(signal.get('raw_content') or 'Not available')[:3000]}

## Scoring Dimensions

{scoring_block}

## Required Output

Return a single JSON object with exactly these fields:

```json
{{
  "signal_type": "<one of: {signal_types}>",
  "relevant_bus": [
    {{"bu_id": "<business-unit-id>", "relevance_score": <0.0-1.0>}}
  ],
  "scores": {{
    "revenue_impact": <1-10>,
    "time_sensitivity": <1-10>,
    "strategic_alignment": <1-10>,
    "competitive_pressure": <1-10>
  }},
  "headline": "<concise action-oriented headline, max 100 chars>",
  "what_summary": "<2-3 sentence factual summary of the signal>",
  "why_it_matters": "<2-3 sentences on specific relevance to the matched VPG BU(s)>",
  "quick_win": "<one specific action to take THIS WEEK, with enough detail to execute>",
  "suggested_owner": "<specific role, e.g. 'VP Sales - Force Sensors'>",
  "estimated_impact": "<revenue range, e.g. '$200K-$500K' or 'Defensive - protect $1M+ account'>",
  "outreach_template": "<optional: 2-3 sentence email/LinkedIn outreach draft if signal_type is revenue-opportunity or partnership-signal, otherwise null>"
}}
```

Rules:
- relevant_bus MUST contain at least one entry
- All score values must be integers from 1 to 10
- headline must be concise and action-oriented
- quick_win must be specific enough to execute this week
- suggested_owner must name a role tied to a specific BU
- Return ONLY the JSON object, no additional text"""


def build_batch_prompt(signals: list[dict]) -> str:
    """Build a prompt for analyzing multiple signals in one API call.

    Used for cost efficiency when processing many signals.

    Args:
        signals: List of signal dicts.

    Returns:
        User prompt requesting an array of structured analyses.
    """
    scoring = get_scoring_weights()
    dims = scoring["scoring_dimensions"]
    dim_descriptions = []
    for dim_id, dim_config in dims.items():
        dim_descriptions.append(f"- {dim_config['label']} (id: {dim_id}, weight: {dim_config['weight']})")
    scoring_block = "\n".join(dim_descriptions)

    signal_types = ", ".join(f'"{t}"' for t in VALID_SIGNAL_TYPES)

    signal_blocks = []
    for i, signal in enumerate(signals):
        signal_blocks.append(
            f"### Signal {i + 1}\n"
            f"**Title:** {signal.get('title', 'N/A')}\n"
            f"**Source:** {signal.get('source_name', 'Unknown')} (Tier {signal.get('source_tier', '?')})\n"
            f"**URL:** {signal.get('url', 'N/A')}\n"
            f"**Summary:** {(signal.get('summary') or 'No summary')[:500]}\n"
        )
    signals_block = "\n".join(signal_blocks)

    return f"""Analyze these {len(signals)} industry signals and produce structured intelligence for each.

## Signals

{signals_block}

## Scoring Dimensions

{scoring_block}

## Required Output

Return a JSON array with one object per signal, in the same order. Each object must have:
- signal_type: one of {signal_types}
- relevant_bus: array of {{"bu_id": "<id>", "relevance_score": <0-1>}}
- scores: {{"revenue_impact": <1-10>, "time_sensitivity": <1-10>, "strategic_alignment": <1-10>, "competitive_pressure": <1-10>}}
- headline: concise action-oriented headline
- what_summary: 2-3 sentence factual summary
- why_it_matters: BU-specific relevance
- quick_win: specific action for this week
- suggested_owner: role tied to a BU
- estimated_impact: revenue range string
- outreach_template: outreach draft or null

Return ONLY a JSON array, no additional text."""
