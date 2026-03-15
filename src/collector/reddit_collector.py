"""Reddit collector for VPG Intelligence Digest.

Monitors subreddits relevant to VPG's industries for signals using PRAW.
Collects posts via both keyword search and hot/new scanning.

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

# Subreddits relevant to VPG's business verticals (fallback if DB is empty)
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
    # Agriculture
    "agriculture",
    "PrecisionAg",
    "farming",
    # Sports & Performance
    "SportsScience",
    "Biomechanics",
    "sportsmedicine",
    # Communication & Telecom
    "telecom",
    "5G",
    "rfelectronics",
    # Infrastructure & Construction
    "Construction",
    "civilengineering",
    "infrastructure",
]

# Minimum upvotes for a post to be considered a signal
MIN_UPVOTES = 5
# Maximum post age in days
MAX_AGE_DAYS = 7
# Max posts to scan per subreddit (hot/new)
MAX_POSTS_PER_SUB = 50
# Max search results per subreddit
MAX_SEARCH_PER_SUB = 25


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
    user_agent = os.getenv("REDDIT_USER_AGENT", "VPG-Intelligence-Agent/3.0")

    if not client_id or not client_secret:
        logger.info("Reddit API credentials not configured — Reddit collection disabled")
        return None

    # Skip placeholder credentials
    if client_id.startswith("your-") or client_secret.startswith("your-"):
        logger.info("Reddit API credentials are placeholders — Reddit collection disabled")
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


def _get_search_queries() -> list[str]:
    """Build search query strings for PRAW subreddit.search().

    Groups keywords into OR-joined queries to maximize coverage.
    """
    # Primary search queries covering VPG's core product areas
    return [
        "load cell OR force sensor OR torque sensor",
        "strain gage OR strain gauge OR stress analysis",
        "foil resistor OR precision resistor OR current sensing",
        "process weighing OR onboard weighing OR truck weighing",
        "rolling mill OR thickness measurement OR laser measurement",
        "crash test sensor OR data acquisition OR DAQ",
        "thermal simulation OR materials testing OR Gleeble",
    ]


def _matches_keywords(text: str, keywords: set[str]) -> list[str]:
    """Check if text matches any monitoring keywords. Returns matched keywords."""
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw in text_lower:
            matched.append(kw)
    return matched


def _post_to_signal(post, subreddit_name: str, matched: list[str]) -> dict:
    """Convert a Reddit post object to a signal dict."""
    created = datetime.utcfromtimestamp(post.created_utc)
    url = f"https://www.reddit.com{post.permalink}"
    text = f"{post.title} {post.selftext or ''}"
    return {
        "external_id": generate_signal_id(url, post.title),
        "title": post.title,
        "summary": (post.selftext or "")[:500],
        "url": url,
        "source_id": f"reddit-{subreddit_name}",
        "source_name": f"Reddit r/{subreddit_name}",
        "source_tier": 3,
        "source_channel": "reddit",
        "published_at": created.isoformat(),
        "image_url": post.thumbnail if post.thumbnail and post.thumbnail.startswith("http") else None,
        "raw_content": text[:2000],
        "reddit_score": post.score,
        "reddit_comments": post.num_comments,
        "matched_keywords": matched,
    }


def _get_active_subreddits_from_db() -> list[str] | None:
    """Read active subreddits from the database. Returns None if unavailable."""
    try:
        from src.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT name FROM reddit_subreddits WHERE active = 1 ORDER BY name"
            ).fetchall()
            if rows:
                return [r[0] for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Could not read subreddits from DB, using defaults: %s", e)
    return None


def collect_from_subreddit(reddit, subreddit_name: str, keywords: set[str],
                           search_queries: list[str] | None = None) -> tuple[list[dict], dict]:
    """Collect keyword-matching posts from a single subreddit.

    Uses both hot/new scanning AND keyword search for maximum coverage.

    Returns:
        Tuple of (signals_list, stats_dict) where stats has:
          - posts_scanned: total posts examined
          - posts_filtered: posts that passed age/upvote filters
          - keyword_matches: posts matching keywords
          - search_matches: posts found via search
          - signals_created: final deduped signal count
    """
    stats = {
        "posts_scanned": 0,
        "posts_filtered": 0,
        "keyword_matches": 0,
        "search_matches": 0,
        "signals_created": 0,
    }
    seen_ids = set()  # Dedup across hot/new/search
    signals = []
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    def _process_post(post, source_label: str) -> bool:
        """Process a single post. Returns True if it became a signal."""
        post_id = getattr(post, "id", None)
        if post_id and post_id in seen_ids:
            return False
        if post_id:
            seen_ids.add(post_id)

        stats["posts_scanned"] += 1

        # Skip old posts
        try:
            created = datetime.utcfromtimestamp(post.created_utc)
        except (AttributeError, TypeError, OSError):
            return False
        if created < cutoff:
            return False

        # Skip low-engagement posts
        if getattr(post, "score", 0) < MIN_UPVOTES:
            return False

        stats["posts_filtered"] += 1

        # Check title + selftext against keywords
        text = f"{post.title} {getattr(post, 'selftext', '') or ''}"
        matched = _matches_keywords(text, keywords)
        if not matched:
            return False

        if source_label == "search":
            stats["search_matches"] += 1
        else:
            stats["keyword_matches"] += 1

        signal = _post_to_signal(post, subreddit_name, matched)
        signals.append(signal)
        return True

    try:
        subreddit = reddit.subreddit(subreddit_name)

        # 1) Scan hot posts
        try:
            for post in subreddit.hot(limit=MAX_POSTS_PER_SUB):
                _process_post(post, "hot")
        except Exception as e:
            logger.debug("r/%s hot scan error: %s", subreddit_name, e)

        # 2) Scan new posts (catches signals that haven't gone hot yet)
        try:
            for post in subreddit.new(limit=MAX_POSTS_PER_SUB):
                _process_post(post, "new")
        except Exception as e:
            logger.debug("r/%s new scan error: %s", subreddit_name, e)

        # 3) Keyword search — uses PRAW's subreddit.search() for targeted results
        if search_queries:
            for query in search_queries:
                try:
                    for post in subreddit.search(query, limit=MAX_SEARCH_PER_SUB,
                                                  time_filter="week", sort="relevance"):
                        _process_post(post, "search")
                except Exception as e:
                    logger.debug("r/%s search '%s' error: %s", subreddit_name, query[:30], e)

    except Exception as e:
        logger.warning("Failed to collect from r/%s: %s", subreddit_name, e)

    stats["signals_created"] = len(signals)
    return signals, stats


def collect_all_reddit(subreddits: list[str] | None = None) -> list[dict]:
    """Collect signals from all configured subreddits.

    Reads active subreddits from the database first; falls back to
    DEFAULT_SUBREDDITS if DB is unavailable or empty.

    Uses both hot/new scanning and keyword search for each subreddit.

    Args:
        subreddits: Override list of subreddit names. If None, reads from DB.

    Returns:
        List of signal dicts ready for database insertion.
    """
    reddit = _get_reddit_client()
    if reddit is None:
        return []

    # Determine subreddits: explicit override > DB > defaults
    if subreddits:
        subs = subreddits
    else:
        db_subs = _get_active_subreddits_from_db()
        subs = db_subs if db_subs else DEFAULT_SUBREDDITS

    keywords = _get_monitoring_keywords()
    search_queries = _get_search_queries()
    logger.info(
        "Reddit collection: scanning %d subreddits with %d keywords, %d search queries",
        len(subs), len(keywords), len(search_queries),
    )

    all_signals = []
    total_stats = {
        "posts_scanned": 0, "posts_filtered": 0,
        "keyword_matches": 0, "search_matches": 0, "signals_created": 0,
    }

    for sub_name in subs:
        signals, stats = collect_from_subreddit(reddit, sub_name, keywords, search_queries)
        if signals:
            logger.info(
                "r/%s: %d signals (scanned=%d, filtered=%d, hot/new=%d, search=%d)",
                sub_name, stats["signals_created"], stats["posts_scanned"],
                stats["posts_filtered"], stats["keyword_matches"], stats["search_matches"],
            )
        else:
            logger.debug(
                "r/%s: 0 signals (scanned=%d, filtered=%d)",
                sub_name, stats["posts_scanned"], stats["posts_filtered"],
            )
        all_signals.extend(signals)

        # Accumulate totals
        for key in total_stats:
            total_stats[key] += stats[key]

    logger.info(
        "Reddit collection complete: %d signals from %d subreddits "
        "(total scanned=%d, filtered=%d, hot/new matches=%d, search matches=%d)",
        total_stats["signals_created"], len(subs),
        total_stats["posts_scanned"], total_stats["posts_filtered"],
        total_stats["keyword_matches"], total_stats["search_matches"],
    )
    return all_signals


def test_single_subreddit(subreddit_name: str) -> dict:
    """Test collection for a single subreddit. Returns detailed results.

    Used by the 'Test Collection' button in the UI for debugging.
    """
    result = {
        "subreddit": subreddit_name,
        "success": False,
        "error": None,
        "credentials_configured": False,
        "praw_installed": False,
        "signals": [],
        "stats": {},
    }

    # Check PRAW
    try:
        import praw  # noqa: F401
        result["praw_installed"] = True
    except ImportError:
        result["error"] = "PRAW not installed. Run: pip install praw"
        return result

    # Check credentials
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret or client_id.startswith("your-"):
        result["error"] = (
            "Reddit API credentials not configured. "
            "Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env file. "
            "Create app at https://www.reddit.com/prefs/apps (type: script)"
        )
        return result
    result["credentials_configured"] = True

    # Try collection
    reddit = _get_reddit_client()
    if reddit is None:
        result["error"] = "Failed to initialize Reddit client"
        return result

    try:
        keywords = _get_monitoring_keywords()
        search_queries = _get_search_queries()
        signals, stats = collect_from_subreddit(reddit, subreddit_name, keywords, search_queries)
        result["success"] = True
        result["stats"] = stats
        result["signals"] = [
            {
                "title": s["title"],
                "url": s["url"],
                "reddit_score": s.get("reddit_score", 0),
                "reddit_comments": s.get("reddit_comments", 0),
                "matched_keywords": s.get("matched_keywords", []),
                "published_at": s.get("published_at", ""),
            }
            for s in signals[:20]  # Cap preview to 20
        ]
    except Exception as e:
        result["error"] = str(e)

    return result
