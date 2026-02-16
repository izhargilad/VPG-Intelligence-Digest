"""Web scraper for VPG Intelligence Digest.

Scrapes websites that don't provide RSS feeds, particularly competitor news pages.
"""

import hashlib
import logging
import time

import requests
from bs4 import BeautifulSoup

from src.config import get_sources

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "VPG-Intelligence-Agent/1.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def generate_signal_id(url: str, title: str) -> str:
    """Generate a unique external ID for deduplication."""
    raw = f"{url}:{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def scrape_page(url: str, timeout: int = 30) -> BeautifulSoup | None:
    """Fetch and parse a web page."""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
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
    """Scrape a single source and return signals."""
    soup = scrape_page(source["url"])
    if not soup:
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
    return signals


def collect_all_scraped() -> list[dict]:
    """Collect signals from all active scrape sources."""
    sources_config = get_sources()
    scrape_config = sources_config.get("scrape_config", {})
    delay = scrape_config.get("request_delay_ms", 2000) / 1000.0
    all_signals = []

    for source in sources_config.get("sources", []):
        if not source.get("active", True):
            continue
        if source.get("type") != "scrape":
            continue

        signals = scrape_source(source)
        all_signals.extend(signals)
        time.sleep(delay)

    logger.info("Total scraped signals collected: %d", len(all_signals))
    return all_signals
