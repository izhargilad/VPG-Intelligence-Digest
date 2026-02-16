"""Main pipeline orchestrator for VPG Intelligence Digest.

Coordinates all 6 pipeline stages:
Collection -> Validation -> Analysis -> Scoring -> Composition -> Delivery
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src.collector.rss_collector import collect_all_rss
from src.collector.web_scraper import collect_all_scraped
from src.analyzer.scorer import score_signal
from src.composer.composer import build_digest_context, render_digest, save_digest_html
from src.config import (
    DELIVERY_MODE,
    LOG_LEVEL,
    LOGS_DIR,
    MOCK_OUTPUT_DIR,
    get_business_units,
    get_recipients,
)
from src.db import (
    complete_pipeline_run,
    get_connection,
    get_signals_by_status,
    init_db,
    insert_pipeline_run,
    insert_signal,
    update_signal_status,
)
from src.delivery.gmail import send_email
from src.validator.validator import validate_signal

logger = logging.getLogger(__name__)


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
        result = validate_signal(conn, signal)
        update_signal_status(conn, signal["id"], "validated")
        validated += 1

    logger.info("Validated %d signals", validated)
    return validated


def stage_score(conn) -> list[dict]:
    """Stage 3 & 4: Score and analyze validated signals."""
    logger.info("=== Stage 3-4: Scoring & Analysis ===")

    validated_signals = get_signals_by_status(conn, "validated")
    scored_signals = []

    for signal in validated_signals:
        analysis = score_signal(signal)
        signal.update(analysis)
        signal["composite_score"] = analysis["composite"]
        update_signal_status(conn, signal["id"], "scored")
        scored_signals.append(signal)

    scored_signals.sort(key=lambda s: s["composite_score"], reverse=True)
    logger.info("Scored %d signals", len(scored_signals))
    return scored_signals


def stage_compose(scored_signals: list[dict]) -> tuple[str, str]:
    """Stage 5: Compose the HTML digest."""
    logger.info("=== Stage 5: Composition ===")

    bu_config = get_business_units()
    context = build_digest_context(scored_signals, bu_config)

    html = render_digest(context)
    subject = context["subject"]

    # Always save a local copy
    output_path = save_digest_html(html, MOCK_OUTPUT_DIR)
    logger.info("Digest composed: %s (%d chars)", subject, len(html))

    return html, subject


def stage_deliver(html: str, subject: str) -> list[dict]:
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
        )
        results.append(result)
        logger.info(
            "Delivery to %s: %s", recipient["email"], result["status"]
        )

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

        # Stage 3-4: Score
        scored_signals = stage_score(conn)

        if not scored_signals:
            logger.warning("No signals to include in digest")
            complete_pipeline_run(
                conn, run_id, "completed",
                signals_collected=collected,
                signals_validated=validated,
                signals_scored=0,
            )
            return {"status": "completed", "signals": 0, "message": "No signals found"}

        # Stage 5: Compose
        html, subject = stage_compose(scored_signals)

        # Stage 6: Deliver
        delivery_results = stage_deliver(html, subject)

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
