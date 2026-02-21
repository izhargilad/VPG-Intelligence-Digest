"""Signal scoring and analysis engine for VPG Intelligence Digest.

Uses the Anthropic API for AI-powered signal classification, scoring,
BU matching, and action card generation. Falls back to keyword-based
heuristics when the API is unavailable.
"""

import logging

from src.analyzer.client import AnalysisClient
from src.analyzer.prompts import (
    VALID_SIGNAL_TYPES,
    build_batch_prompt,
    build_signal_prompt,
    build_system_prompt,
)
from src.config import get_business_units, get_scoring_weights

logger = logging.getLogger(__name__)

# Module-level client instance (lazy-initialized)
_client: AnalysisClient | None = None


def _get_client() -> AnalysisClient:
    """Get or create the shared AnalysisClient instance."""
    global _client
    if _client is None:
        _client = AnalysisClient()
    return _client


def calculate_composite_score(scores: dict) -> float:
    """Calculate weighted composite score from dimension scores.

    Args:
        scores: Dict with keys matching scoring dimension IDs and float values (1-10).

    Returns:
        Weighted composite score (1-10).
    """
    weights = get_scoring_weights()
    dimensions = weights["scoring_dimensions"]

    composite = 0.0
    for dim_id, dim_config in dimensions.items():
        weight = dim_config["weight"]
        score = scores.get(dim_id, 0)
        composite += weight * score

    return round(composite, 2)


def match_signal_to_bus(signal: dict) -> list[dict]:
    """Match a signal to relevant business units based on keywords.

    Used as a fallback when AI analysis is unavailable, and as a
    pre-filter to validate AI BU assignments.

    Args:
        signal: Signal dict with 'title', 'summary'.

    Returns:
        List of dicts with 'bu_id' and 'relevance_score'.
    """
    bu_config = get_business_units()
    text = f"{signal.get('title', '')} {signal.get('summary', '')}".lower()

    matches = []
    for bu in bu_config.get("business_units", []):
        if not bu.get("active", True):
            continue

        score = 0.0
        keywords = bu.get("monitoring_keywords", [])
        products = bu.get("key_products", [])
        industries = bu.get("core_industries", [])
        all_keywords = keywords + products + industries
        matched_keywords = []

        for keyword in all_keywords:
            if keyword.lower() in text:
                score += 1.0
                matched_keywords.append(keyword)

        # Normalize: even 1-2 keyword matches should give a meaningful score
        if all_keywords and matched_keywords:
            score = min(0.4 + (score / max(len(all_keywords) * 0.25, 1)) * 0.6, 1.0)

        if score > 0:
            matches.append({
                "bu_id": bu["id"],
                "relevance_score": round(score, 3),
                "matched_keywords": matched_keywords,
            })

    matches.sort(key=lambda x: x["relevance_score"], reverse=True)
    return matches


def _validate_ai_result(result: dict) -> dict | None:
    """Validate and normalize the AI analysis result.

    Ensures all required fields are present and values are within expected ranges.

    Returns:
        Validated result dict, or None if critically invalid.
    """
    if not isinstance(result, dict):
        return None

    # Validate signal_type
    signal_type = result.get("signal_type", "")
    if signal_type not in VALID_SIGNAL_TYPES:
        logger.warning("Invalid signal_type '%s', defaulting to 'market-shift'", signal_type)
        result["signal_type"] = "market-shift"

    # Validate relevant_bus
    bus = result.get("relevant_bus", [])
    if not bus or not isinstance(bus, list):
        return None  # Critical: every signal must map to a BU

    for bu_match in bus:
        bu_match["relevance_score"] = max(0.0, min(1.0, float(bu_match.get("relevance_score", 0.5))))

    # Validate scores
    scores = result.get("scores", {})
    required_dims = ["revenue_impact", "time_sensitivity", "strategic_alignment", "competitive_pressure"]
    for dim in required_dims:
        val = scores.get(dim, 5)
        scores[dim] = max(1, min(10, int(round(float(val)))))
    result["scores"] = scores

    # Ensure required text fields have defaults
    result.setdefault("headline", "Industry Signal Detected")
    result.setdefault("what_summary", "Signal details pending review.")
    result.setdefault("why_it_matters", "Relevance assessment in progress.")
    result.setdefault("quick_win", "Review signal and assess BU impact.")
    result.setdefault("suggested_owner", "BU Manager")
    # Only default to TBD if we truly have nothing — never show TBD in final output
    if not result.get("estimated_impact") or result.get("estimated_impact") == "TBD":
        rev_score = scores.get("revenue_impact", 5)
        if rev_score >= 8:
            result["estimated_impact"] = "$1M-$5M potential revenue impact"
        elif rev_score >= 6:
            result["estimated_impact"] = "$500K-$2M potential revenue impact"
        elif rev_score >= 4:
            result["estimated_impact"] = "$200K-$500K potential revenue impact"
        else:
            result["estimated_impact"] = "$100K-$200K potential revenue impact"
    result.setdefault("outreach_template", None)

    return result


def score_signal_ai(signal: dict, client: AnalysisClient | None = None) -> dict | None:
    """Score a signal using the Anthropic API.

    Args:
        signal: Signal dict with title, summary, url, source info.
        client: Optional AnalysisClient instance (uses shared instance if None).

    Returns:
        Analysis result dict with scores, BU matches, and action card fields,
        or None if AI analysis fails.
    """
    client = client or _get_client()
    if not client.available:
        return None

    system_prompt = build_system_prompt()
    user_prompt = build_signal_prompt(signal)

    raw_result = client.analyze(system_prompt, user_prompt)
    if raw_result is None:
        return None

    result = _validate_ai_result(raw_result)
    if result is None:
        logger.error("AI result validation failed for signal: %s", signal.get("title", "?")[:60])
        return None

    # Calculate composite score from the AI-provided dimension scores
    result["composite"] = calculate_composite_score(result["scores"])

    # Map relevant_bus to the standard bu_matches format
    result["bu_matches"] = [
        {"bu_id": bu["bu_id"], "relevance_score": bu["relevance_score"]}
        for bu in result["relevant_bus"]
    ]

    result["analysis_method"] = "ai"
    logger.info(
        "AI scored signal: %.1f - %s [%s]",
        result["composite"],
        result["headline"][:50],
        result["signal_type"],
    )
    return result


def _estimate_impact_heuristic(signal: dict, signal_type: str, scores: dict) -> str:
    """Generate an estimated revenue impact from signal content and scores.

    Parses dollar amounts from the signal text, and infers a range based
    on signal type and revenue_impact score.
    """
    import re
    text = f"{signal.get('title', '')} {signal.get('summary', '')}".lower()

    # Try to extract explicit dollar amounts from the text
    dollar_amounts = []
    for match in re.finditer(r'\$[\d,.]+\s*[bmk]?\b', text):
        raw = match.group()
        multiplier = 1
        if raw.endswith('b'):
            multiplier = 1_000_000_000
        elif raw.endswith('m'):
            multiplier = 1_000_000
        elif raw.endswith('k'):
            multiplier = 1_000
        num_str = re.sub(r'[^\d.]', '', raw)
        try:
            dollar_amounts.append(float(num_str) * multiplier)
        except ValueError:
            pass

    if dollar_amounts:
        max_amt = max(dollar_amounts)
        if max_amt >= 1_000_000_000:
            return f"${max_amt/1e9:.0f}B+ market opportunity"
        if max_amt >= 1_000_000:
            return f"${max_amt/1e6:.0f}M+ opportunity"
        if max_amt >= 1_000:
            return f"${max_amt/1e3:.0f}K+ opportunity"

    # Infer from signal type and revenue_impact score
    rev_score = scores.get("revenue_impact", 5)

    if signal_type == "competitive-threat":
        if rev_score >= 7:
            return "Defensive — protect $1M+ revenue"
        return "Defensive — protect $500K+ revenue"

    if signal_type == "trade-tariff":
        if rev_score >= 7:
            return "Cost advantage — $1M+ competitive benefit"
        return "Cost advantage — $200K-$500K competitive benefit"

    # Revenue-based estimate for other types
    if rev_score >= 8:
        return "$1M-$5M potential revenue impact"
    if rev_score >= 6:
        return "$500K-$2M potential revenue impact"
    if rev_score >= 4:
        return "$200K-$500K potential revenue impact"
    return "$100K-$200K potential revenue impact"


def _generate_heuristic_why(signal: dict, signal_type: str, bu_matches: list[dict]) -> str:
    """Generate a meaningful 'why it matters' from signal content and BU matches."""
    bu_config = get_business_units()
    bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

    matched_bus = [bu_names.get(m["bu_id"], m["bu_id"]) for m in bu_matches[:3]]
    bu_str = ", ".join(matched_bus) if matched_bus else "VPG business units"

    type_reasons = {
        "competitive-threat": f"A competitor move has been detected that could affect {bu_str}. Monitoring competitor positioning and preparing a defensive response is advised.",
        "revenue-opportunity": f"This signal points to a potential revenue opportunity relevant to {bu_str}. Early engagement could secure first-mover advantage.",
        "trade-tariff": f"Trade policy changes could create a cost advantage for VPG's India production hub relative to China-dependent competitors, benefiting {bu_str}.",
        "partnership-signal": f"A potential partnership or alliance opportunity has been identified that aligns with {bu_str} strategic priorities.",
        "technology-trend": f"An emerging technology trend could impact {bu_str} product roadmaps or create new market opportunities.",
        "customer-intelligence": f"Customer activity signals suggest {bu_str} should evaluate account strategy and prepare updated talking points.",
        "market-shift": f"Industry dynamics are shifting in a way that could create both risks and opportunities for {bu_str}.",
    }
    return type_reasons.get(signal_type, f"This development is relevant to {bu_str} and warrants review.")


def _generate_heuristic_quick_win(signal_type: str) -> str:
    """Generate a relevant quick-win action based on signal type."""
    actions = {
        "competitive-threat": "Brief sales team on competitive positioning. Prepare counter-messaging for affected accounts.",
        "revenue-opportunity": "Identify decision-maker contacts and prepare an initial outreach draft within the week.",
        "trade-tariff": "Quantify cost advantage vs. China-sourced competitors and update pricing models.",
        "partnership-signal": "Research the partner's strategic priorities and identify mutual value propositions.",
        "technology-trend": "Map current product capabilities against the emerging trend. Identify gaps and content opportunities.",
        "customer-intelligence": "Schedule internal account review and prepare updated talking points for the next customer interaction.",
        "market-shift": "Circulate this signal to the BU leadership team for impact assessment and response planning.",
    }
    return actions.get(signal_type, "Review the signal details and assess relevance to current BU priorities.")


def _generate_heuristic_owner(signal_type: str) -> str:
    """Assign a relevant owner role based on signal type."""
    owners = {
        "competitive-threat": "VP Sales / Product Marketing",
        "revenue-opportunity": "BU Sales Director",
        "trade-tariff": "VP Operations / Supply Chain",
        "partnership-signal": "VP Business Development",
        "technology-trend": "CTO / Product Engineering Lead",
        "customer-intelligence": "Key Account Manager",
        "market-shift": "BU General Manager",
    }
    return owners.get(signal_type, "BU Manager")


def score_signal_heuristic(signal: dict) -> dict:
    """Score a signal using keyword-based heuristics (fallback).

    Args:
        signal: Signal dict.

    Returns:
        Dict with dimension scores, composite score, and BU matches.
    """
    bu_matches = match_signal_to_bus(signal)

    # Classify signal type from keywords
    text = f"{signal.get('title', '')} {signal.get('summary', '')}".lower()
    signal_type = "market-shift"
    if any(w in text for w in ["competitor", "competes", "launch", "threat", "rival"]):
        signal_type = "competitive-threat"
    elif any(w in text for w in ["rfi", "rfp", "order", "partner", "revenue", "opportunity", "seeking"]):
        signal_type = "revenue-opportunity"
    elif any(w in text for w in ["tariff", "trade", "duty", "import", "export"]):
        signal_type = "trade-tariff"
    elif any(w in text for w in ["acqui", "partner", "alliance", "joint venture"]):
        signal_type = "partnership-signal"
    elif any(w in text for w in ["patent", "innovation", "breakthrough", "technology"]):
        signal_type = "technology-trend"

    # Base scores — moderate defaults; signals must earn their way in
    # through keyword matches and type boosting
    base_revenue = 5
    base_time = 5
    base_competitive = 4

    # Boost based on signal type
    if signal_type == "competitive-threat":
        base_competitive = 7
        base_time = 7
    elif signal_type == "revenue-opportunity":
        base_revenue = 7
        base_time = 7
    elif signal_type == "trade-tariff":
        base_revenue = 7
        base_competitive = 6
    elif signal_type == "partnership-signal":
        base_revenue = 6
    elif signal_type == "technology-trend":
        base_revenue = 5

    # Strategic alignment from keyword matching — only scores well if
    # the signal actually matches VPG BU keywords/products/industries
    if bu_matches:
        alignment = max(4, min(int(bu_matches[0]["relevance_score"] * 10), 10))
    else:
        alignment = 3

    scores = {
        "revenue_impact": base_revenue,
        "time_sensitivity": base_time,
        "strategic_alignment": alignment,
        "competitive_pressure": base_competitive,
    }

    composite = calculate_composite_score(scores)

    return {
        "scores": scores,
        "composite": composite,
        "bu_matches": bu_matches,
        "signal_type": signal_type,
        "headline": signal.get("title", ""),
        "what_summary": signal.get("summary", ""),
        "why_it_matters": _generate_heuristic_why(signal, signal_type, bu_matches),
        "quick_win": _generate_heuristic_quick_win(signal_type),
        "suggested_owner": _generate_heuristic_owner(signal_type),
        "estimated_impact": _estimate_impact_heuristic(signal, signal_type, scores),
        "outreach_template": None,
        "analysis_method": "heuristic",
    }


def score_signal(signal: dict, client: AnalysisClient | None = None) -> dict:
    """Score a signal, using AI when available with heuristic fallback.

    This is the main entry point for signal scoring. It tries AI analysis
    first, and falls back to keyword heuristics if the API is unavailable
    or returns an error.

    Args:
        signal: Signal dict.
        client: Optional AnalysisClient instance.

    Returns:
        Analysis result dict with all action card fields populated.
    """
    # Try AI scoring first
    result = score_signal_ai(signal, client)
    if result is not None:
        return result

    # Fallback to heuristics
    logger.info("Falling back to heuristic scoring for: %s", signal.get("title", "?")[:60])
    return score_signal_heuristic(signal)


def score_batch_ai(signals: list[dict], client: AnalysisClient | None = None) -> list[dict]:
    """Score a batch of signals in a single API call for efficiency.

    Falls back to individual scoring if batch parsing fails.

    Args:
        signals: List of signal dicts.
        client: Optional AnalysisClient instance.

    Returns:
        List of analysis result dicts in the same order as input.
    """
    client = client or _get_client()
    if not client.available or not signals:
        return [score_signal_heuristic(s) for s in signals]

    system_prompt = build_system_prompt()
    user_prompt = build_batch_prompt(signals)

    raw_result = client.analyze(system_prompt, user_prompt)

    if raw_result is None or not isinstance(raw_result, list):
        logger.warning("Batch analysis failed, falling back to individual scoring")
        return [score_signal(s, client) for s in signals]

    if len(raw_result) != len(signals):
        logger.warning(
            "Batch result count mismatch (%d vs %d), falling back to individual",
            len(raw_result), len(signals),
        )
        return [score_signal(s, client) for s in signals]

    results = []
    for i, (signal, raw) in enumerate(zip(signals, raw_result)):
        validated = _validate_ai_result(raw)
        if validated is None:
            logger.warning("Batch result %d invalid, scoring individually", i)
            validated = score_signal(signal, client)
        else:
            validated["composite"] = calculate_composite_score(validated["scores"])
            validated["bu_matches"] = [
                {"bu_id": bu["bu_id"], "relevance_score": bu["relevance_score"]}
                for bu in validated.get("relevant_bus", [])
            ]
            validated["analysis_method"] = "ai-batch"
        results.append(validated)

    return results
