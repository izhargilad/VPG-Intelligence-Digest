"""Signal validation engine for VPG Intelligence Digest.

Cross-references each signal against independent sources to meet
the 3-source validation requirement.
"""

import logging
from urllib.parse import urlparse

from src.db import get_validation_count, insert_validation

logger = logging.getLogger(__name__)


def get_source_domain(url: str) -> str:
    """Extract the domain from a URL for publisher independence check."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def find_corroborating_sources(signal: dict, max_results: int = 5) -> list[dict]:
    """Search for corroborating sources for a signal.

    This is a placeholder that will be enhanced with actual search
    implementation in Phase 2. For now, it provides the framework.

    Args:
        signal: Signal dict to validate.
        max_results: Maximum corroborating sources to find.

    Returns:
        List of corroboration dicts with 'url', 'source', 'title', 'similarity_score'.
    """
    # TODO: Implement actual web search for corroboration
    # Options: Google Custom Search API, Bing Search API, or news API
    logger.info(
        "Validation search for: %s (implementation pending)",
        signal.get("title", "")[:60],
    )
    return []


def validate_signal(conn, signal: dict) -> dict:
    """Validate a single signal by finding corroborating sources.

    Args:
        conn: Database connection.
        signal: Signal dict (must include 'id' and 'url').

    Returns:
        Validation result dict with 'level', 'source_count', 'corroborations'.
    """
    signal_id = signal["id"]
    original_domain = get_source_domain(signal["url"])

    corroborations = find_corroborating_sources(signal)

    # Filter out same-publisher sources
    independent = []
    for corr in corroborations:
        corr_domain = get_source_domain(corr["url"])
        if corr_domain != original_domain:
            independent.append(corr)

    # Store validations in DB
    for corr in independent:
        insert_validation(conn, signal_id, corr)

    # Determine validation level (original counts as 1 source)
    existing_count = get_validation_count(conn, signal_id)
    total_sources = max(1 + len(independent), 1 + existing_count)

    if total_sources >= 3:
        level = "verified"
    elif total_sources >= 2:
        level = "likely"
    else:
        level = "unverified"

    logger.info("Signal %d: %s (%d sources)", signal_id, level, total_sources)

    return {
        "level": level,
        "source_count": total_sources,
        "corroborations": independent,
    }


def validate_batch(conn, signals: list[dict]) -> list[dict]:
    """Validate a batch of signals."""
    results = []
    for signal in signals:
        result = validate_signal(conn, signal)
        result["signal_id"] = signal["id"]
        results.append(result)
    return results
