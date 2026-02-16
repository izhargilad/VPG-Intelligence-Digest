"""Signal scoring and analysis engine.

Scores signals on 4 dimensions and generates action cards.
Phase 1: keyword-based heuristic scoring.
Phase 2: Anthropic API-powered scoring and action generation.
"""

import logging

from src.config import get_business_units, get_scoring_weights

logger = logging.getLogger(__name__)


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

    Args:
        signal: Signal dict with 'title', 'summary', 'source_id'.

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
        matched_keywords = []

        for keyword in keywords:
            if keyword.lower() in text:
                score += 1.0
                matched_keywords.append(keyword)

        if keywords:
            score = min(score / max(len(keywords) * 0.3, 1), 1.0)

        if score > 0:
            matches.append({
                "bu_id": bu["id"],
                "relevance_score": round(score, 3),
                "matched_keywords": matched_keywords,
            })

    matches.sort(key=lambda x: x["relevance_score"], reverse=True)
    return matches


def score_signal(signal: dict) -> dict:
    """Score a signal using keyword-based heuristics (Phase 1).

    Will be replaced by Anthropic API scoring in Phase 2.

    Args:
        signal: Signal dict.

    Returns:
        Dict with dimension scores, composite score, and BU matches.
    """
    bu_matches = match_signal_to_bus(signal)

    scores = {
        "revenue_impact": 5.0,
        "time_sensitivity": 5.0,
        "strategic_alignment": min(bu_matches[0]["relevance_score"] * 10, 10.0) if bu_matches else 2.0,
        "competitive_pressure": 5.0,
    }

    composite = calculate_composite_score(scores)

    return {
        "scores": scores,
        "composite": composite,
        "bu_matches": bu_matches,
        "signal_type": "market-shift",  # Default; AI will classify in Phase 2
        "headline": signal.get("title", ""),
        "what_summary": signal.get("summary", ""),
        "why_it_matters": "Relevance analysis pending (Phase 2 - AI integration)",
        "quick_win": "Review signal and assess BU impact",
        "suggested_owner": "BU Manager",
        "estimated_impact": "TBD",
    }
