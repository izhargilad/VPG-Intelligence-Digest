"""Web scraper for VPG Intelligence Digest.

Scrapes websites that don't provide RSS feeds, particularly competitor news pages.
Validates URLs before scraping and tracks source health via error counts.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.config import get_sources

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "VPG-Intelligence-Agent/1.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_ERROR_COUNT = 5


def generate_signal_id(url: str, title: str) -> str:
    """Generate a unique external ID for deduplication."""
    raw = f"{url}:{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


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
    """Reset error_count to 0 on successful scrape."""
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


def scrape_page(url: str, timeout: int = 30) -> BeautifulSoup | None:
    """Fetch and parse a web page.

    Logs specific HTTP error codes (404, 403, etc.) for easier debugging.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if response.status_code == 404:
            logger.error("SCRAPE 404 NOT FOUND: %s", url)
            return None
        if response.status_code == 403:
            logger.warning("SCRAPE 403 FORBIDDEN: %s", url)
            return None
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.Timeout:
        logger.error("SCRAPE TIMEOUT: %s (no response within %ds)", url, timeout)
        return None
    except requests.ConnectionError as e:
        logger.error("SCRAPE UNREACHABLE: %s — %s", url, e)
        return None
    except requests.RequestException as e:
        logger.error("Failed to scrape %s: %s", url, str(e))
        return None


def extract_articles(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract article links and titles from a parsed page.

    Uses common patterns for news/blog pages.
    """
    articles = []
    seen_urls = set()

    # Strategy 1: Look for <article> tags
    for article in soup.find_all("article"):
        link = article.find("a", href=True)
        title_el = article.find(["h1", "h2", "h3", "h4"])
        if link and title_el:
            url = link["href"]
            if not url.startswith("http"):
                url = base_url.rstrip("/") + "/" + url.lstrip("/")
            if url not in seen_urls:
                seen_urls.add(url)
                summary_el = article.find("p")
                articles.append({
                    "title": title_el.get_text(strip=True),
                    "url": url,
                    "summary": summary_el.get_text(strip=True) if summary_el else "",
                })

    # Strategy 2: Look for h2/h3 tags with links
    if not articles:
        for heading in soup.find_all(["h2", "h3"]):
            link = heading.find("a", href=True)
            if link:
                url = link["href"]
                if not url.startswith("http"):
                    url = base_url.rstrip("/") + "/" + url.lstrip("/")
                if url not in seen_urls:
                    seen_urls.add(url)
                    articles.append({
                        "title": link.get_text(strip=True),
                        "url": url,
                        "summary": "",
                    })

    return articles


def scrape_source(source: dict) -> list[dict]:
    """Scrape a single source and return signals.

    Tracks error counts: increments on failure, resets on success.
    Sources are auto-disabled after MAX_ERROR_COUNT consecutive failures.
    """
    # Skip auto-disabled sources
    if source.get("error_count", 0) >= MAX_ERROR_COUNT:
        logger.info("Skipping auto-disabled source: %s (error_count=%d)", source["id"], source["error_count"])
        return []

    soup = scrape_page(source["url"])
    if not soup:
        _increment_error_count(source)
        return []

    articles = extract_articles(soup, source["url"])
    signals = []

    for article in articles:
        signal = {
            "external_id": generate_signal_id(article["url"], article["title"]),
            "title": article["title"],
            "summary": article.get("summary", ""),
            "url": article["url"],
            "source_id": source["id"],
            "source_name": source["name"],
            "source_tier": source.get("tier", 2),
            "published_at": None,
            "image_url": None,
        }
        signals.append(signal)

    logger.info("Scraped %d articles from %s", len(signals), source["name"])
    _reset_error_count(source)
    return signals


def collect_all_scraped() -> list[dict]:
    """Collect signals from all active scrape sources."""
    sources_config = get_sources()
    scrape_config = sources_config.get("scrape_config", {})
    delay = scrape_config.get("request_delay_ms", 2000) / 1000.0
    all_signals = []

    for source in sources_config.get("sources", []):
        if not source.get("active", True):
            logger.info("Skipping inactive source: %s", source["id"])
            continue
        if source.get("type") != "scrape":
            continue

        signals = scrape_source(source)
        all_signals.extend(signals)
        time.sleep(delay)

    logger.info("Total scraped signals collected: %d", len(all_signals))
    return all_signals
