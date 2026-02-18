"""Main pipeline orchestrator for VPG Intelligence Digest.

Coordinates all 6 pipeline stages:
Collection -> Validation -> Analysis -> Scoring -> Composition -> Delivery
"""

import logging
import sys
from datetime import datetime

from src.analyzer.client import AnalysisClient
from src.analyzer.scorer import score_batch_ai, score_signal
from src.collector.rss_collector import collect_all_rss
from src.collector.web_scraper import collect_all_scraped
from src.composer.composer import build_digest_context, render_digest, save_digest_html
from src.config import (
    DELIVERY_MODE,
    LOG_LEVEL,
    LOGS_DIR,
    MOCK_OUTPUT_DIR,
    get_business_units,
    get_recipients,
    get_scoring_weights,
)
from src.db import (
    complete_pipeline_run,
    get_connection,
    get_signals_by_status,
    init_db,
    insert_analysis,
    insert_pipeline_run,
    insert_signal,
    save_signal_bus,
    update_signal_status,
)
from src.delivery.gmail import send_email
from src.trends.tracker import update_trends
from src.validator.validator import validate_signal

logger = logging.getLogger(__name__)

# Batch size for AI analysis (balance cost vs. reliability)
AI_BATCH_SIZE = 10


def setup_logging() -> None:
    """Configure logging for the pipeline."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"pipeline_{timestamp}.log"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def stage_collect(conn) -> int:
    """Stage 1: Collect signals from all sources."""
    logger.info("=== Stage 1: Collection ===")

    rss_signals = collect_all_rss()
    scraped_signals = collect_all_scraped()
    all_signals = rss_signals + scraped_signals

    inserted = 0
    for signal in all_signals:
        row_id = insert_signal(conn, signal)
        if row_id:
            inserted += 1

    logger.info("Collected %d signals, %d new", len(all_signals), inserted)
    return inserted


def stage_validate(conn) -> int:
    """Stage 2: Validate new signals against 3+ sources."""
    logger.info("=== Stage 2: Validation ===")

    new_signals = get_signals_by_status(conn, "new")
    validated = 0

    for signal in new_signals:
        validate_signal(conn, signal)
        update_signal_status(conn, signal["id"], "validated")
        validated += 1

    logger.info("Validated %d signals", validated)
    return validated


def stage_score(conn) -> list[dict]:
    """Stage 3 & 4: Score and analyze validated signals with AI.

    Uses Anthropic API for analysis when available, with heuristic fallback.
    Processes signals in batches for cost efficiency.
    """
    logger.info("=== Stage 3-4: AI Scoring & Analysis ===")

    validated_signals = get_signals_by_status(conn, "validated")
    if not validated_signals:
        return []

    # Initialize the AI client
    client = AnalysisClient()
    if client.available:
        logger.info("Anthropic API available — using AI scoring")
    else:
        logger.warning("Anthropic API unavailable — using heuristic fallback")

    # Get scoring thresholds
    thresholds = get_scoring_weights().get("thresholds", {})
    min_score = thresholds.get("include_in_digest", 4.0)

    scored_signals = []

    # Process in batches for API efficiency
    for i in range(0, len(validated_signals), AI_BATCH_SIZE):
        batch = validated_signals[i:i + AI_BATCH_SIZE]

        if client.available and len(batch) > 1:
            # Batch AI scoring
            results = score_batch_ai(batch, client)
        else:
            # Individual scoring (AI with fallback)
            results = [score_signal(s, client) for s in batch]

        for signal, analysis in zip(batch, results):
            signal.update(analysis)
            signal["composite_score"] = analysis["composite"]

            # Persist analysis to DB
            insert_analysis(conn, signal["id"], analysis)
            save_signal_bus(conn, signal["id"], analysis.get("bu_matches", []))
            update_signal_status(conn, signal["id"], "scored")

            # Only include signals above the threshold
            if analysis["composite"] >= min_score:
                scored_signals.append(signal)
            else:
                logger.debug(
                    "Signal below threshold (%.1f < %.1f): %s",
                    analysis["composite"], min_score, signal.get("title", "?")[:50],
                )

    scored_signals.sort(key=lambda s: s["composite_score"], reverse=True)

    ai_count = sum(1 for s in scored_signals if s.get("analysis_method", "").startswith("ai"))
    logger.info(
        "Scored %d signals (%d AI, %d heuristic), %d above threshold",
        len(validated_signals), ai_count, len(validated_signals) - ai_count,
        len(scored_signals),
    )
    return scored_signals


def stage_compose(scored_signals: list[dict]) -> tuple[str, str, dict]:
    """Stage 5: Compose the HTML digest.

    Returns:
        Tuple of (html, subject, cid_images) where cid_images is a dict
        of CID -> image data for MIME embedding.
    """
    logger.info("=== Stage 5: Composition ===")

    bu_config = get_business_units()
    context = build_digest_context(scored_signals, bu_config)

    html = render_digest(context)
    subject = context["subject"]
    cid_images = context.get("cid_images", {})

    # Always save a local copy
    save_digest_html(html, MOCK_OUTPUT_DIR)
    logger.info("Digest composed: %s (%d chars)", subject, len(html))

    return html, subject, cid_images


def stage_deliver(html: str, subject: str, cid_images: dict | None = None) -> list[dict]:
    """Stage 6: Deliver the digest to recipients."""
    logger.info("=== Stage 6: Delivery (mode: %s) ===", DELIVERY_MODE)

    recipients_config = get_recipients()
    results = []

    for recipient in recipients_config.get("recipients", []):
        if recipient.get("status") != "active":
            continue

        result = send_email(
            to=recipient["email"],
            subject=subject,
            html_content=html,
            cid_images=cid_images,
        )
        results.append(result)
        logger.info("Delivery to %s: %s", recipient["email"], result["status"])

    sent = sum(1 for r in results if r["status"] == "sent")
    logger.info("Delivered to %d/%d recipients", sent, len(results))
    return results


def run_full_pipeline() -> dict:
    """Execute the complete 6-stage pipeline."""
    setup_logging()
    logger.info("Starting VPG Intelligence Digest pipeline")

    conn = get_connection()
    init_db()

    run_id = insert_pipeline_run(conn, "full")

    try:
        # Stage 1: Collect
        collected = stage_collect(conn)

        # Stage 2: Validate
        validated = stage_validate(conn)

        # Stage 3-4: AI Score
        scored_signals = stage_score(conn)

        if not scored_signals:
            logger.warning("No signals above threshold for digest")
            complete_pipeline_run(
                conn, run_id, "completed",
                signals_collected=collected,
                signals_validated=validated,
                signals_scored=0,
            )
            return {"status": "completed", "signals": 0, "message": "No signals above threshold"}

        # Trend analysis (runs after scoring, before composition)
        logger.info("=== Trend Analysis ===")
        trend_result = update_trends(conn)
        logger.info("Trends: %d updated, %d notable", trend_result["trends_updated"], len(trend_result["notable"]))

        # Stage 5: Compose
        html, subject, cid_images = stage_compose(scored_signals)

        # Stage 6: Deliver
        delivery_results = stage_deliver(html, subject, cid_images)

        complete_pipeline_run(
            conn, run_id, "completed",
            signals_collected=collected,
            signals_validated=validated,
            signals_scored=len(scored_signals),
        )

        logger.info("Pipeline completed successfully")
        return {
            "status": "completed",
            "signals_collected": collected,
            "signals_validated": validated,
            "signals_scored": len(scored_signals),
            "delivery_results": delivery_results,
        }

    except Exception as e:
        logger.error("Pipeline failed: %s", str(e), exc_info=True)
        complete_pipeline_run(conn, run_id, "failed", error_message=str(e))
        return {"status": "failed", "error": str(e)}

    finally:
        conn.close()


if __name__ == "__main__":
    run_full_pipeline()
