"""RSS feed collector for VPG Intelligence Digest.

Parses RSS/Atom feeds from configured sources and extracts signals.
"""

import hashlib
import logging
from datetime import datetime

import feedparser

from src.config import get_sources

logger = logging.getLogger(__name__)


def generate_signal_id(url: str, title: str) -> str:
    """Generate a unique external ID for deduplication."""
    raw = f"{url}:{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def collect_from_feed(source: dict) -> list[dict]:
    """Collect signals from a single RSS feed source.

    Args:
        source: Source config dict with 'url', 'id', 'name', 'tier', etc.

    Returns:
        List of signal dicts ready for database insertion.
    """
    signals = []
    try:
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            logger.warning("Feed parse error for %s: %s", source["id"], feed.bozo_exception)
            return signals

        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            published = entry.get("published_parsed") or entry.get("updated_parsed")
            published_at = None
            if published:
                try:
                    published_at = datetime(*published[:6]).isoformat()
                except (ValueError, TypeError):
                    pass

            # Extract image from media content or enclosures
            image_url = None
            if hasattr(entry, "media_content") and entry.media_content:
                for media in entry.media_content:
                    if media.get("medium") == "image" or media.get("type", "").startswith("image"):
                        image_url = media.get("url")
                        break
            if not image_url and hasattr(entry, "enclosures"):
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image"):
                        image_url = enc.get("href")
                        break

            signal = {
                "external_id": generate_signal_id(url, title),
                "title": title,
                "summary": entry.get("summary", ""),
                "url": url,
                "source_id": source["id"],
                "source_name": source["name"],
                "source_tier": source.get("tier", 2),
                "published_at": published_at,
                "image_url": image_url,
            }
            signals.append(signal)

        logger.info("Collected %d signals from %s", len(signals), source["name"])

    except Exception as e:
        logger.error("Failed to collect from %s: %s", source["id"], str(e))

    return signals


def collect_all_rss() -> list[dict]:
    """Collect signals from all active RSS sources.

    Returns:
        List of all collected signal dicts.
    """
    sources_config = get_sources()
    all_signals = []

    for source in sources_config.get("sources", []):
        if not source.get("active", True):
            continue
        if source.get("type") != "rss":
            continue

        signals = collect_from_feed(source)
        all_signals.extend(signals)

    logger.info("Total RSS signals collected: %d", len(all_signals))
    return all_signals
