"""Self-improving keyword expansion based on feedback patterns.

Automatically activates/deactivates keywords based on recipient feedback:
- Keywords in highly-rated signals get boosted (auto-activated)
- Keywords in consistently low-rated signals get demoted (auto-deactivated)
- New keyword candidates are extracted from positively-rated signals

This creates a self-improving collection loop where the system learns
which topics are valuable to recipients over time.
"""

import logging
import re
from collections import Counter, defaultdict

from src.db import get_connection

logger = logging.getLogger(__name__)

# Minimum feedback count before keyword adjustments
MIN_FEEDBACK_FOR_KEYWORD_ADJUSTMENT = 5
# Positive rate thresholds
ACTIVATE_THRESHOLD = 0.7   # Auto-activate keywords with >70% positive rate
DEACTIVATE_THRESHOLD = 0.3  # Auto-deactivate keywords with <30% positive rate
# Max new keywords to suggest per run
MAX_NEW_SUGGESTIONS = 20


def expand_keywords_from_feedback(conn=None, dry_run: bool = False) -> dict:
    """Analyze feedback to auto-adjust keyword activation and suggest new keywords.

    Args:
        conn: DB connection (created if None)
        dry_run: If True, compute changes but don't apply them

    Returns:
        Dict with activated, deactivated, and suggested keywords.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        activated = _auto_activate_keywords(conn, dry_run)
        deactivated = _auto_deactivate_keywords(conn, dry_run)
        suggestions = _extract_keyword_candidates(conn)

        return {
            "activated": activated,
            "deactivated": deactivated,
            "suggestions": suggestions,
            "dry_run": dry_run,
            "summary": {
                "keywords_activated": len(activated),
                "keywords_deactivated": len(deactivated),
                "new_suggestions": len(suggestions),
            },
        }

    finally:
        if close_conn:
            conn.close()


def _auto_activate_keywords(conn, dry_run: bool) -> list[dict]:
    """Find inactive keywords that appear in positively-rated signals and activate them."""
    rows = conn.execute("""
        SELECT k.keyword, k.id, COUNT(*) as total,
               SUM(CASE WHEN f.rating = 'up' THEN 1 ELSE 0 END) as positive
        FROM keywords k
        JOIN signals s ON (LOWER(s.title) LIKE '%' || LOWER(k.keyword) || '%'
                           OR LOWER(s.summary) LIKE '%' || LOWER(k.keyword) || '%')
        JOIN feedback f ON f.signal_id = s.id
        WHERE k.active = 0
        GROUP BY k.keyword, k.id
        HAVING total >= ?
    """, (MIN_FEEDBACK_FOR_KEYWORD_ADJUSTMENT,)).fetchall()

    activated = []
    for row in rows:
        keyword, kw_id, total, positive = row
        rate = positive / total if total else 0
        if rate >= ACTIVATE_THRESHOLD:
            if not dry_run:
                conn.execute("UPDATE keywords SET active = 1 WHERE id = ?", (kw_id,))
                conn.commit()
            activated.append({
                "keyword": keyword,
                "positive_rate": round(rate * 100, 1),
                "feedback_count": total,
            })
            logger.info("Auto-activated keyword '%s' (%.0f%% positive, %d feedback)", keyword, rate * 100, total)

    return activated


def _auto_deactivate_keywords(conn, dry_run: bool) -> list[dict]:
    """Find active keywords that consistently appear in negatively-rated signals."""
    rows = conn.execute("""
        SELECT k.keyword, k.id, COUNT(*) as total,
               SUM(CASE WHEN f.rating = 'up' THEN 1 ELSE 0 END) as positive
        FROM keywords k
        JOIN signals s ON (LOWER(s.title) LIKE '%' || LOWER(k.keyword) || '%'
                           OR LOWER(s.summary) LIKE '%' || LOWER(k.keyword) || '%')
        JOIN feedback f ON f.signal_id = s.id
        WHERE k.active = 1 AND k.source != 'manual'
        GROUP BY k.keyword, k.id
        HAVING total >= ?
    """, (MIN_FEEDBACK_FOR_KEYWORD_ADJUSTMENT,)).fetchall()

    deactivated = []
    for row in rows:
        keyword, kw_id, total, positive = row
        rate = positive / total if total else 0
        if rate <= DEACTIVATE_THRESHOLD:
            if not dry_run:
                conn.execute("UPDATE keywords SET active = 0 WHERE id = ?", (kw_id,))
                conn.commit()
            deactivated.append({
                "keyword": keyword,
                "positive_rate": round(rate * 100, 1),
                "feedback_count": total,
            })
            logger.info("Auto-deactivated keyword '%s' (%.0f%% positive, %d feedback)", keyword, rate * 100, total)

    return deactivated


def _extract_keyword_candidates(conn) -> list[dict]:
    """Extract new keyword candidates from positively-rated signals.

    Looks for frequently occurring terms in highly-rated signals that
    don't match any existing keywords.
    """
    rows = conn.execute("""
        SELECT s.title, s.summary
        FROM signals s
        JOIN feedback f ON f.signal_id = s.id
        WHERE f.rating = 'up'
        ORDER BY f.created_at DESC
        LIMIT 100
    """).fetchall()

    if not rows:
        return []

    # Extract meaningful terms (2-3 word phrases)
    term_counts = Counter()
    for row in rows:
        text = f"{row[0] or ''} {row[1] or ''}".lower()
        # Extract 2-3 word phrases
        words = re.findall(r'\b[a-z]{3,}\b', text)
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            term_counts[bigram] += 1
            if i + 2 < len(words):
                trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
                term_counts[trigram] += 1

    # Filter out terms that already exist as keywords
    existing = set()
    for row in conn.execute("SELECT LOWER(keyword) FROM keywords").fetchall():
        existing.add(row[0])

    # Common stopword bigrams to exclude
    stopwords = {"the", "and", "for", "that", "this", "with", "from", "have", "has",
                 "are", "was", "were", "will", "not", "but", "its", "can", "all"}

    candidates = []
    for term, count in term_counts.most_common(MAX_NEW_SUGGESTIONS * 3):
        if term in existing:
            continue
        words = term.split()
        if any(w in stopwords for w in words):
            continue
        if count >= 3:
            candidates.append({
                "keyword": term,
                "occurrences": count,
                "source": "feedback-expansion",
            })
        if len(candidates) >= MAX_NEW_SUGGESTIONS:
            break

    return candidates
