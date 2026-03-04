"""Google Trends collector for VPG Intelligence Digest.

Uses pytrends to monitor keyword popularity trends relevant to VPG's industries.
Identifies rising search interest that may indicate emerging market opportunities
or competitive shifts.

Falls back gracefully if pytrends is not installed.
"""

import hashlib
import logging
from datetime import datetime

from src.config import get_industries, get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)


def generate_signal_id(keyword: str, timeframe: str) -> str:
    """Generate a unique external ID for a trend signal."""
    raw = f"gtrends:{keyword}:{timeframe}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _get_pytrends_client():
    """Create a pytrends TrendReq client. Returns None if unavailable."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed — Google Trends collection disabled. pip install pytrends")
        return None

    try:
        client = TrendReq(hl="en-US", tz=300)  # US Eastern
        return client
    except Exception as e:
        logger.error("Failed to initialize pytrends client: %s", e)
        return None


def _get_trend_keyword_groups() -> list[dict]:
    """Build keyword groups from industries config.

    Google Trends limits to 5 keywords per request, so we group them by industry.
    Returns a list of dicts with 'industry_id', 'industry_name', 'keywords' (max 5).
    """
    groups = []
    try:
        config = get_industries()
        for ind in config.get("industries", []):
            if not ind.get("active", True):
                continue
            kws = ind.get("keywords", [])
            if not kws:
                continue
            # Take up to 5 most relevant keywords per industry
            selected = kws[:5]
            groups.append({
                "industry_id": ind["id"],
                "industry_name": ind["name"],
                "keywords": selected,
            })
    except Exception as e:
        logger.warning("Could not load industries for Google Trends: %s", e)

    return groups


def fetch_interest_over_time(pytrends, keywords: list[str],
                             timeframe: str = "now 7-d") -> dict | None:
    """Fetch interest over time for a set of keywords.

    Args:
        pytrends: TrendReq client.
        keywords: List of up to 5 keywords.
        timeframe: Pytrends timeframe string.

    Returns:
        Dict with keyword -> {avg_interest, trend_direction, peak_interest, data_points}.
    """
    try:
        pytrends.build_payload(keywords, timeframe=timeframe, geo="US")
        df = pytrends.interest_over_time()

        if df.empty:
            return None

        results = {}
        for kw in keywords:
            if kw not in df.columns:
                continue
            series = df[kw]
            avg_interest = float(series.mean())
            peak = float(series.max())

            # Determine trend direction by comparing first/second half
            mid = len(series) // 2
            if mid > 0:
                first_half = float(series[:mid].mean())
                second_half = float(series[mid:].mean())
                if second_half > first_half * 1.2:
                    direction = "rising"
                elif second_half < first_half * 0.8:
                    direction = "declining"
                else:
                    direction = "stable"
            else:
                direction = "stable"

            results[kw] = {
                "avg_interest": round(avg_interest, 1),
                "peak_interest": round(peak, 1),
                "trend_direction": direction,
                "data_points": len(series),
            }

        return results

    except Exception as e:
        logger.warning("Google Trends fetch failed for %s: %s", keywords, e)
        return None


def fetch_related_queries(pytrends, keywords: list[str]) -> dict:
    """Fetch related queries for keyword discovery.

    Returns:
        Dict mapping keyword -> list of related query strings.
    """
    try:
        pytrends.build_payload(keywords, timeframe="today 3-m", geo="US")
        related = pytrends.related_queries()

        results = {}
        for kw in keywords:
            if kw not in related or related[kw] is None:
                continue
            rising = related[kw].get("rising")
            top = related[kw].get("top")

            queries = []
            if rising is not None and not rising.empty:
                queries.extend(rising["query"].tolist()[:10])
            if top is not None and not top.empty:
                queries.extend(top["query"].tolist()[:5])

            # Deduplicate
            results[kw] = list(dict.fromkeys(queries))

        return results

    except Exception as e:
        logger.warning("Related queries fetch failed: %s", e)
        return {}


def collect_google_trends() -> list[dict]:
    """Collect signals from Google Trends for all industry keyword groups.

    Only generates signals for keywords showing 'rising' interest,
    as those represent potential opportunities or threats.

    Returns:
        List of signal dicts ready for database insertion.
    """
    pytrends = _get_pytrends_client()
    if pytrends is None:
        return []

    groups = _get_trend_keyword_groups()
    if not groups:
        logger.info("No keyword groups configured for Google Trends")
        return []

    logger.info("Google Trends: scanning %d industry keyword groups", len(groups))

    signals = []
    timeframe = "now 7-d"

    for group in groups:
        interest = fetch_interest_over_time(pytrends, group["keywords"], timeframe)
        if not interest:
            continue

        # Only create signals for rising keywords
        rising_keywords = [
            (kw, data) for kw, data in interest.items()
            if data["trend_direction"] == "rising" and data["avg_interest"] > 20
        ]

        for kw, data in rising_keywords:
            title = f"Rising search interest: '{kw}' ({group['industry_name']})"
            summary = (
                f"Google Trends shows rising search interest for '{kw}' "
                f"(avg: {data['avg_interest']}, peak: {data['peak_interest']}) "
                f"in the {group['industry_name']} vertical. "
                f"This may indicate emerging market activity, new product launches, "
                f"or increased buyer interest relevant to VPG."
            )

            signal = {
                "external_id": generate_signal_id(kw, timeframe),
                "title": title,
                "summary": summary,
                "url": f"https://trends.google.com/trends/explore?q={kw.replace(' ', '+')}&geo=US",
                "source_id": "google-trends",
                "source_name": "Google Trends",
                "source_tier": 3,
                "published_at": datetime.now().isoformat(),
                "image_url": None,
                "trend_data": data,
                "industry_id": group["industry_id"],
            }
            signals.append(signal)
            logger.info(
                "Trend signal: '%s' rising (avg=%.1f, peak=%.1f) in %s",
                kw, data["avg_interest"], data["peak_interest"], group["industry_name"],
            )

    logger.info("Google Trends collection complete: %d rising signals", len(signals))
    return signals


def get_trend_snapshot(keywords: list[str] | None = None,
                       timeframe: str = "now 7-d") -> dict:
    """Get a snapshot of current Google Trends data for specific keywords.

    Useful for on-demand trend checks from the API.

    Args:
        keywords: Keywords to check (max 5). Uses top industry keywords if None.
        timeframe: Pytrends timeframe string.

    Returns:
        Dict with keyword interest data and related queries.
    """
    pytrends = _get_pytrends_client()
    if pytrends is None:
        return {"error": "pytrends not available", "keywords": {}}

    if not keywords:
        groups = _get_trend_keyword_groups()
        keywords = []
        for g in groups[:3]:
            keywords.extend(g["keywords"][:2])
        keywords = keywords[:5]

    if not keywords:
        return {"error": "No keywords to check", "keywords": {}}

    interest = fetch_interest_over_time(pytrends, keywords, timeframe)
    related = fetch_related_queries(pytrends, keywords)

    return {
        "timeframe": timeframe,
        "checked_at": datetime.now().isoformat(),
        "keywords": interest or {},
        "related_queries": related,
    }
