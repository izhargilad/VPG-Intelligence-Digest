"""Reddit collector for VPG Intelligence Digest.

Monitors subreddits relevant to VPG's industries for signals using PRAW.
Extracts posts and comments that match configured keywords.

Requires Reddit API credentials:
  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
in .env file.

Falls back gracefully if PRAW is not installed or credentials are missing.
"""

import hashlib
import logging
import os
from datetime import datetime, timedelta

from src.config import get_industries

logger = logging.getLogger(__name__)

# Subreddits relevant to VPG's business verticals
DEFAULT_SUBREDDITS = [
    # Robotics & Automation
    "robotics",
    "Automate",
    "ROS",
    # Aerospace & Defense
    "aerospace",
    "DefenseIndustry",
    # Automotive & EV
    "electricvehicles",
    "SelfDrivingCars",
    "automotive",
    # Steel & Metals / Manufacturing
    "metalworking",
    "manufacturing",
    "Machinists",
    # Sensors & Instrumentation
    "electronics",
    "sensors",
    "ECE",
    # Materials Science
    "materials",
    "MaterialsScience",
    # Test & Measurement
    "engineering",
    # Trade & Tariffs
    "SupplyChain",
    "Economics",
    # Mining & Heavy Equipment
    "mining",
    "HeavyEquipment",
]

# Minimum upvotes for a post to be considered a signal
MIN_UPVOTES = 5
# Maximum post age in days
MAX_AGE_DAYS = 7
# Max posts to scan per subreddit
MAX_POSTS_PER_SUB = 50


def generate_signal_id(url: str, title: str) -> str:
    """Generate a unique external ID for deduplication."""
    raw = f"{url}:{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _get_reddit_client():
    """Create a PRAW Reddit client from env vars. Returns None if unavailable."""
    try:
        import praw
    except ImportError:
        logger.warning("PRAW not installed — Reddit collection disabled. pip install praw")
        return None

    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "VPG-Intelligence-Agent/2.1")

    if not client_id or not client_secret:
        logger.info("Reddit API credentials not configured — Reddit collection disabled")
        return None

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        # Verify credentials work (read-only mode)
        reddit.read_only = True
        return reddit
    except Exception as e:
        logger.error("Failed to initialize Reddit client: %s", e)
        return None


def _get_monitoring_keywords() -> set[str]:
    """Build a set of monitoring keywords from industries config."""
    keywords = set()
    try:
        config = get_industries()
        for ind in config.get("industries", []):
            if ind.get("active", True):
                for kw in ind.get("keywords", []):
                    keywords.add(kw.lower())
    except Exception:
        pass

    # Always include core VPG-relevant terms
    core_terms = {
        "load cell", "force sensor", "strain gage", "strain gauge",
        "foil resistor", "torque sensor", "process weighing",
        "onboard weighing", "crash test", "data acquisition",
        "rolling mill", "thickness measurement", "gleeble",
    }
    keywords.update(core_terms)
    return keywords


def _matches_keywords(text: str, keywords: set[str]) -> list[str]:
    """Check if text matches any monitoring keywords. Returns matched keywords."""
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw in text_lower:
            matched.append(kw)
    return matched


def collect_from_subreddit(reddit, subreddit_name: str, keywords: set[str]) -> list[dict]:
    """Collect keyword-matching posts from a single subreddit."""
    signals = []
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    try:
        subreddit = reddit.subreddit(subreddit_name)
        for post in subreddit.hot(limit=MAX_POSTS_PER_SUB):
            # Skip old posts
            created = datetime.utcfromtimestamp(post.created_utc)
            if created < cutoff:
                continue

            # Skip low-engagement posts
            if post.score < MIN_UPVOTES:
                continue

            # Check title + selftext against keywords
            text = f"{post.title} {post.selftext or ''}"
            matched = _matches_keywords(text, keywords)
            if not matched:
                continue

            url = f"https://www.reddit.com{post.permalink}"
            signal = {
                "external_id": generate_signal_id(url, post.title),
                "title": post.title,
                "summary": (post.selftext or "")[:500],
                "url": url,
                "source_id": f"reddit-{subreddit_name}",
                "source_name": f"Reddit r/{subreddit_name}",
                "source_tier": 3,
                "published_at": created.isoformat(),
                "image_url": post.thumbnail if post.thumbnail and post.thumbnail.startswith("http") else None,
                "raw_content": text[:2000],
                "reddit_score": post.score,
                "reddit_comments": post.num_comments,
                "matched_keywords": matched,
            }
            signals.append(signal)

    except Exception as e:
        logger.warning("Failed to collect from r/%s: %s", subreddit_name, e)

    return signals


def collect_all_reddit(subreddits: list[str] | None = None) -> list[dict]:
    """Collect signals from all configured subreddits.

    Args:
        subreddits: Override list of subreddit names. Uses defaults if None.

    Returns:
        List of signal dicts ready for database insertion.
    """
    reddit = _get_reddit_client()
    if reddit is None:
        return []

    subs = subreddits or DEFAULT_SUBREDDITS
    keywords = _get_monitoring_keywords()
    logger.info("Reddit collection: scanning %d subreddits with %d keywords", len(subs), len(keywords))

    all_signals = []
    for sub_name in subs:
        signals = collect_from_subreddit(reddit, sub_name, keywords)
        if signals:
            logger.info("r/%s: %d matching signals", sub_name, len(signals))
        all_signals.extend(signals)

    logger.info("Reddit collection complete: %d signals from %d subreddits", len(all_signals), len(subs))
    return all_signals
