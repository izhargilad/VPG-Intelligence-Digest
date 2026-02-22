"""RSS feed collector for VPG Intelligence Digest.

Parses RSS/Atom feeds from configured sources and extracts signals.
Pre-validates feed URLs with an HTTP check to catch 404/403 errors
before passing to feedparser.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import feedparser
import requests

from src.config import get_sources

logger = logging.getLogger(__name__)

# Max consecutive errors before auto-disabling a source
MAX_ERROR_COUNT = 5
HTTP_TIMEOUT = 15  # seconds


def generate_signal_id(url: str, title: str) -> str:
    """Generate a unique external ID for deduplication."""
    raw = f"{url}:{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _preflight_check(url: str, source_id: str) -> bool:
    """Verify a feed URL is reachable and returns valid content.

    Returns True if the URL looks like a valid feed, False otherwise.
    """
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "VPG-Intelligence-Agent/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        })

        if resp.status_code == 404:
            logger.error("SOURCE 404 NOT FOUND: %s (%s) — disabling", source_id, url)
            return False
        if resp.status_code == 403:
            logger.warning("SOURCE 403 FORBIDDEN: %s (%s) — may require auth or different user-agent", source_id, url)
            return False
        if resp.status_code >= 400:
            logger.error("SOURCE HTTP %d: %s (%s)", resp.status_code, source_id, url)
            return False

        # Check content type — RSS/Atom should be XML-ish
        content_type = resp.headers.get("content-type", "").lower()
        is_feed = any(t in content_type for t in ["xml", "rss", "atom", "text/plain"])

        # Also check first bytes for XML signature
        body_start = resp.text[:500].strip().lower()
        looks_like_xml = body_start.startswith("<?xml") or "<rss" in body_start or "<feed" in body_start

        if not is_feed and not looks_like_xml:
            logger.warning(
                "SOURCE NOT A FEED: %s (%s) — content-type: %s (looks like a web page, not RSS/Atom)",
                source_id, url, content_type,
            )
            return False

        return True
    except requests.Timeout:
        logger.error("SOURCE TIMEOUT: %s (%s) — no response within %ds", source_id, url, HTTP_TIMEOUT)
        return False
    except requests.ConnectionError as e:
        logger.error("SOURCE UNREACHABLE: %s (%s) — %s", source_id, url, e)
        return False
    except requests.RequestException as e:
        logger.error("SOURCE CHECK FAILED: %s (%s) — %s", source_id, url, e)
        return False


def _increment_error_count(source: dict) -> None:
    """Increment the error_count for a source in the config file."""
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "sources.json"
        if not config_path.exists():
            return
        config = json.loads(config_path.read_text())
        for src in config.get("sources", []):
            if src["id"] == source["id"]:
                src["error_count"] = src.get("error_count", 0) + 1
                if src["error_count"] >= MAX_ERROR_COUNT:
                    src["active"] = False
                    logger.warning(
                        "AUTO-DISABLED source %s after %d consecutive errors",
                        src["id"], src["error_count"],
                    )
                break
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    except Exception as e:
        logger.debug("Could not update error_count for %s: %s", source["id"], e)


def _reset_error_count(source: dict) -> None:
    """Reset error_count to 0 on successful collection."""
    if source.get("error_count", 0) == 0:
        return
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "sources.json"
        if not config_path.exists():
            return
        config = json.loads(config_path.read_text())
        for src in config.get("sources", []):
            if src["id"] == source["id"]:
                src["error_count"] = 0
                break
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    except Exception as e:
        logger.debug("Could not reset error_count for %s: %s", source["id"], e)


def collect_from_feed(source: dict) -> list[dict]:
    """Collect signals from a single RSS feed source.

    Pre-validates the URL with an HTTP check, then parses with feedparser.

    Args:
        source: Source config dict with 'url', 'id', 'name', 'tier', etc.

    Returns:
        List of signal dicts ready for database insertion.
    """
    signals = []

    # Skip sources that have been auto-disabled
    if source.get("error_count", 0) >= MAX_ERROR_COUNT:
        logger.info("Skipping auto-disabled source: %s (error_count=%d)", source["id"], source["error_count"])
        return signals

    # Pre-flight: verify URL returns valid feed content
    if not _preflight_check(source["url"], source["id"]):
        _increment_error_count(source)
        return signals

    try:
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            logger.warning("Feed parse error for %s: %s", source["id"], feed.bozo_exception)
            _increment_error_count(source)
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
        _reset_error_count(source)

    except Exception as e:
        logger.error("Failed to collect from %s: %s", source["id"], str(e))
        _increment_error_count(source)

    return signals


def collect_all_rss() -> list[dict]:
    """Collect signals from all active RSS sources.

    Returns:
        List of all collected signal dicts.
    """
    sources_config = get_sources()
    all_signals = []
    succeeded = 0
    failed = 0

    for source in sources_config.get("sources", []):
        if not source.get("active", True):
            logger.info("Skipping inactive source: %s", source["id"])
            continue
        if source.get("type") != "rss":
            continue

        signals = collect_from_feed(source)
        if signals:
            succeeded += 1
        else:
            failed += 1
        all_signals.extend(signals)

    logger.info(
        "RSS collection complete: %d signals from %d sources (%d failed)",
        len(all_signals), succeeded, failed,
    )
    return all_signals
