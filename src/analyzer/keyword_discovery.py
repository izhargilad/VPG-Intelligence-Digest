"""Auto-keyword discovery engine for VPG Intelligence Digest.

Analyzes collected signals to discover new keywords that should be monitored.
Implements the "Self-Improving Keyword Expansion" feature from the brief:
- When signals from a keyword are consistently rated highly, expand monitoring
- When signals are consistently low-rated, deprioritize
- Discover new keywords from signal text that co-occur with known keywords

Runs after each pipeline scoring stage to refine the keyword universe.
"""

import logging
import re
from collections import Counter
from datetime import datetime

from src.db import get_connection, get_all_keywords, upsert_keyword, bulk_import_keywords

logger = logging.getLogger(__name__)

# Words to exclude from keyword candidates
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "that", "this", "these", "those", "it", "its", "they", "them", "their",
    "we", "our", "you", "your", "he", "she", "him", "her", "his",
    "not", "no", "nor", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "only", "also", "than", "too",
    "very", "just", "about", "above", "after", "again", "between",
    "into", "through", "during", "before", "since", "until", "while",
    "which", "what", "when", "where", "who", "whom", "how", "why",
    "new", "said", "says", "according", "company", "year", "percent",
    "million", "billion", "market", "industry", "report", "global",
    "will", "first", "last", "next", "like", "well", "even", "many",
    "much", "over", "under", "up", "down", "out", "off", "then",
    "now", "here", "there", "still", "get", "got", "make", "made",
}

# Minimum occurrences to consider a term as a keyword candidate
MIN_OCCURRENCES = 3
# Minimum score of signals containing a candidate for it to be promoted
MIN_AVG_SCORE = 6.0
# Maximum new keywords to discover per run
MAX_NEW_KEYWORDS_PER_RUN = 20


def _extract_ngrams(text: str, n: int = 2) -> list[str]:
    """Extract n-grams from text, filtering stop words."""
    words = re.findall(r'\b[a-z][a-z\-]+[a-z]\b', text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    ngrams = []
    # Unigrams (single meaningful words)
    if n >= 1:
        for w in words:
            if len(w) >= 4:  # Only longer words as standalone keywords
                ngrams.append(w)

    # Bigrams
    if n >= 2:
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            ngrams.append(bigram)

    # Trigrams
    if n >= 3:
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            ngrams.append(trigram)

    return ngrams


def discover_keywords_from_signals(conn=None, min_score: float = MIN_AVG_SCORE,
                                   max_new: int = MAX_NEW_KEYWORDS_PER_RUN) -> dict:
    """Analyze recent scored signals to discover new keyword candidates.

    Extracts n-grams from high-scoring signal text, compares against
    existing keywords, and suggests new ones.

    Args:
        conn: DB connection (creates one if None).
        min_score: Minimum average signal score for a keyword to be promoted.
        max_new: Maximum new keywords to discover per run.

    Returns:
        Dict with 'discovered' (new keywords) and 'stats'.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        # Get existing keywords to avoid duplicates
        existing_kws = get_all_keywords(conn, active_only=False)
        existing_set = {kw["keyword"].lower() for kw in existing_kws}

        # Get recently scored signals with their scores
        rows = conn.execute("""
            SELECT s.id, s.title, s.summary, s.raw_content,
                   sa.score_composite, sa.signal_type, sa.headline
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            WHERE s.status IN ('scored', 'published')
              AND sa.score_composite >= ?
            ORDER BY sa.score_composite DESC
            LIMIT 500
        """, (min_score * 0.7,)).fetchall()

        if not rows:
            logger.info("No scored signals available for keyword discovery")
            return {"discovered": [], "stats": {"signals_analyzed": 0}}

        # Extract all n-grams from high-scoring signals
        ngram_counter = Counter()
        ngram_scores = {}  # track average score per ngram

        for row in rows:
            text = f"{row[1]} {row[2] or ''} {row[3] or ''} {row[6] or ''}"
            score = row[4] or 0

            ngrams = _extract_ngrams(text, n=2)
            for ng in ngrams:
                ngram_counter[ng] += 1
                if ng not in ngram_scores:
                    ngram_scores[ng] = []
                ngram_scores[ng].append(score)

        # Filter candidates: must appear multiple times, not already known, decent score
        candidates = []
        for ngram, count in ngram_counter.most_common(200):
            if count < MIN_OCCURRENCES:
                continue
            if ngram in existing_set:
                continue
            # Skip very short or very long terms
            if len(ngram) < 4 or len(ngram) > 50:
                continue

            avg_score = sum(ngram_scores[ngram]) / len(ngram_scores[ngram])
            if avg_score < min_score:
                continue

            candidates.append({
                "keyword": ngram,
                "occurrences": count,
                "avg_score": round(avg_score, 2),
                "source": "auto-discovered",
            })

        # Sort by a composite of frequency and score
        candidates.sort(key=lambda c: c["occurrences"] * c["avg_score"], reverse=True)
        discovered = candidates[:max_new]

        logger.info(
            "Keyword discovery: analyzed %d signals, found %d candidates, selected %d",
            len(rows), len(candidates), len(discovered),
        )

        return {
            "discovered": discovered,
            "stats": {
                "signals_analyzed": len(rows),
                "total_candidates": len(candidates),
                "selected": len(discovered),
                "existing_keywords": len(existing_set),
                "timestamp": datetime.now().isoformat(),
            },
        }

    finally:
        if close_conn:
            conn.close()


def auto_import_discovered(conn=None, min_score: float = MIN_AVG_SCORE,
                           max_new: int = MAX_NEW_KEYWORDS_PER_RUN,
                           auto_activate: bool = False) -> dict:
    """Discover and import new keywords into the database.

    Discovered keywords are inserted with source='auto-discovered'.
    They are inactive by default (require manual review) unless auto_activate=True.

    Args:
        conn: DB connection.
        min_score: Minimum average score threshold.
        max_new: Maximum new keywords to import.
        auto_activate: If True, new keywords are immediately active.

    Returns:
        Dict with imported keywords and stats.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        result = discover_keywords_from_signals(conn, min_score, max_new)
        discovered = result["discovered"]

        imported = 0
        for candidate in discovered:
            try:
                upsert_keyword(conn, {
                    "keyword": candidate["keyword"],
                    "industry_id": None,  # Unassigned — can be mapped via UI
                    "source": "auto-discovered",
                    "active": auto_activate,
                })
                imported += 1
            except Exception as e:
                logger.debug("Could not import keyword '%s': %s", candidate["keyword"], e)

        result["stats"]["imported"] = imported
        logger.info("Auto-imported %d discovered keywords", imported)
        return result

    finally:
        if close_conn:
            conn.close()


def update_keyword_hit_counts(conn=None) -> int:
    """Update hit_count for all keywords based on signal matches.

    Scans recent signals and increments hit_count for each keyword
    found in signal text. Used by the feedback loop to identify
    high-performing vs low-performing keywords.

    Returns:
        Number of keywords with updated hit counts.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        keywords = get_all_keywords(conn, active_only=True)
        if not keywords:
            return 0

        # Get recent signal text
        rows = conn.execute("""
            SELECT s.title, s.summary, s.raw_content
            FROM signals s
            WHERE s.status IN ('scored', 'published')
            ORDER BY s.collected_at DESC
            LIMIT 500
        """).fetchall()

        if not rows:
            return 0

        # Build a combined text corpus
        corpus = ""
        for row in rows:
            corpus += f" {row[0]} {row[1] or ''} {row[2] or ''}"
        corpus_lower = corpus.lower()

        updated = 0
        now = datetime.now().isoformat()
        for kw in keywords:
            count = corpus_lower.count(kw["keyword"].lower())
            if count > 0:
                conn.execute(
                    "UPDATE keywords SET hit_count = hit_count + ?, last_hit_at = ? WHERE id = ?",
                    (count, now, kw["id"]),
                )
                updated += 1

        conn.commit()
        logger.info("Updated hit counts for %d/%d keywords", updated, len(keywords))
        return updated

    finally:
        if close_conn:
            conn.close()
