#!/usr/bin/env python3
"""Reddit collection diagnostic — run this to identify why signals are zero.

Usage:
    python -m scripts.reddit_diagnose
    # or from project root:
    python scripts/reddit_diagnose.py
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


def check_praw_installed():
    """Check if PRAW is installed."""
    try:
        import praw  # noqa: F401
        print(f"  PRAW version: {praw.__version__}")
        return True
    except ImportError:
        print("  PRAW not installed")
        print("  -> Fix: pip install praw")
        return False


def check_env():
    """Check if Reddit credentials exist in .env"""
    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
    optional = ["REDDIT_USER_AGENT"]

    all_ok = True
    for key in required:
        val = os.environ.get(key, "")
        if not val or val.startswith("your-"):
            print(f"  {key}: MISSING or placeholder")
            all_ok = False
        else:
            print(f"  {key}: configured ({val[:8]}...)")

    for key in optional:
        val = os.environ.get(key, "")
        if val:
            print(f"  {key}: {val}")
        else:
            print(f"  {key}: not set (will use default)")

    if not all_ok:
        print("\n  -> Fix: Create a Reddit app at https://www.reddit.com/prefs/apps")
        print("     Choose 'script' type, then add credentials to .env:")
        print("     REDDIT_CLIENT_ID=your_client_id")
        print("     REDDIT_CLIENT_SECRET=your_secret")
    return all_ok


def check_authentication():
    """Check if PRAW can authenticate."""
    import praw

    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "VPG-Intelligence-Agent/3.0")

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        reddit.read_only = True
        # Test by fetching a known subreddit
        sub = reddit.subreddit("robotics")
        _ = sub.display_name  # This triggers the actual API call
        print(f"  Authenticated in read-only mode")
        print(f"  Test subreddit r/robotics accessible: {sub.display_name}")
        return reddit
    except Exception as e:
        print(f"  Authentication failed: {e}")
        return None


def check_subreddit_access(reddit):
    """Check if we can actually read from configured subreddits."""
    test_subs = ["robotics", "engineering", "manufacturing", "sensors", "aerospace"]
    accessible = 0
    for sub_name in test_subs:
        try:
            sub = reddit.subreddit(sub_name)
            posts = list(sub.hot(limit=3))
            print(f"  r/{sub_name}: accessible, {len(posts)} hot posts")
            accessible += 1
        except Exception as e:
            print(f"  r/{sub_name}: FAILED - {e}")
    return accessible


def check_keyword_matching(reddit):
    """Test if keyword search returns results."""
    queries = [
        ("robotics", "load cell OR force sensor OR torque sensor"),
        ("engineering", "strain gage OR strain gauge OR data acquisition"),
        ("manufacturing", "process weighing OR rolling mill"),
    ]
    total_results = 0
    for sub_name, query in queries:
        try:
            sub = reddit.subreddit(sub_name)
            results = list(sub.search(query, limit=5, time_filter="month"))
            total_results += len(results)
            print(f"  r/{sub_name} search '{query[:40]}...': {len(results)} results")
            for r in results[:2]:
                print(f"    -> {r.title[:70]}... (score: {r.score})")
        except Exception as e:
            print(f"  r/{sub_name} search failed: {e}")
    return total_results


def check_database():
    """Check subreddits in database."""
    try:
        from src.db import get_connection
        conn = get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM reddit_subreddits").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM reddit_subreddits WHERE active = 1"
            ).fetchone()[0]
            signal_count = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE source_id LIKE 'reddit-%'"
            ).fetchone()[0]
            scored = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE source_id LIKE 'reddit-%' "
                "AND status IN ('scored', 'published')"
            ).fetchone()[0]
            print(f"  Subreddits in DB: {total} total, {active} active")
            print(f"  Reddit signals in DB: {signal_count} total, {scored} scored/published")

            # Show top subreddits by signal count
            rows = conn.execute(
                "SELECT source_name, COUNT(*) as cnt FROM signals "
                "WHERE source_id LIKE 'reddit-%' "
                "GROUP BY source_name ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            if rows:
                print(f"  Top subreddits by signals:")
                for r in rows:
                    print(f"    {r[0]}: {r[1]} signals")
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"  Database check failed: {e}")
        return False


def run_test_collection():
    """Run a quick test collection on one subreddit."""
    try:
        from src.collector.reddit_collector import test_single_subreddit
        print("  Testing collection on r/robotics...")
        result = test_single_subreddit("robotics")
        if result["success"]:
            stats = result["stats"]
            print(f"  Scanned: {stats['posts_scanned']} posts")
            print(f"  Passed filters: {stats['posts_filtered']}")
            print(f"  Keyword matches (hot/new): {stats['keyword_matches']}")
            print(f"  Search matches: {stats['search_matches']}")
            print(f"  Signals created: {stats['signals_created']}")
            for s in result["signals"][:3]:
                print(f"    -> {s['title'][:70]}...")
                print(f"       Keywords: {', '.join(s['matched_keywords'][:3])}")
        else:
            print(f"  Test collection failed: {result['error']}")
        return result["success"]
    except Exception as e:
        print(f"  Test collection error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("VPG Reddit Collection Diagnostic")
    print("=" * 60)

    print("\n[1/6] Checking PRAW installation...")
    if not check_praw_installed():
        print("\nFix PRAW installation first, then re-run.")
        sys.exit(1)

    print("\n[2/6] Checking environment variables...")
    env_ok = check_env()

    print("\n[3/6] Checking database...")
    check_database()

    if not env_ok:
        print("\nFix environment variables first, then re-run.")
        print("See: https://www.reddit.com/prefs/apps")
        sys.exit(1)

    print("\n[4/6] Testing authentication...")
    reddit = check_authentication()
    if not reddit:
        print("\nFix authentication first, then re-run.")
        sys.exit(1)

    print("\n[5/6] Testing subreddit access...")
    check_subreddit_access(reddit)

    print("\n[6/6] Testing keyword search...")
    check_keyword_matching(reddit)

    print("\n[BONUS] Running test collection...")
    run_test_collection()

    print("\n" + "=" * 60)
    print("Diagnostic complete.")
