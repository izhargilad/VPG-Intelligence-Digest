"""Main pipeline orchestrator for VPG Intelligence Digest.

Coordinates all 6 pipeline stages:
Collection -> Validation -> Analysis -> Scoring -> Composition -> Delivery

Supports pause/resume/cancel via shared state and PDF delivery mode.
"""

import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

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


# ── Pipeline control state (shared with API server) ──────────────────

class PipelineControl:
    """Thread-safe pipeline control for pause/resume/cancel."""

    def __init__(self):
        self._lock = threading.Lock()
        self._paused = False
        self._cancelled = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._current_stage = ""

    def pause(self):
        with self._lock:
            self._paused = True
            self._pause_event.clear()

    def resume(self):
        with self._lock:
            self._paused = False
            self._pause_event.set()

    def cancel(self):
        with self._lock:
            self._cancelled = True
            self._pause_event.set()  # Unblock if paused

    def reset(self):
        with self._lock:
            self._paused = False
            self._cancelled = False
            self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def current_stage(self) -> str:
        return self._current_stage

    @current_stage.setter
    def current_stage(self, value: str):
        self._current_stage = value

    def check_point(self):
        """Call between stages to support pause/cancel.

        Blocks while paused, raises if cancelled.
        """
        self._pause_event.wait()  # Blocks if paused
        if self._cancelled:
            raise PipelineCancelled("Pipeline cancelled by user")


class PipelineCancelled(Exception):
    """Raised when a pipeline run is cancelled by the user."""
    pass


# Global pipeline control instance (used by API server)
pipeline_control = PipelineControl()


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
    """Stage 1: Collect signals from all sources.

    New signals are inserted with status 'new'. If a signal already
    exists (same external_id from a prior run), its status is reset
    to 'new' so it gets reprocessed with current scoring weights.
    """
    logger.info("=== Stage 1: Collection ===")
    pipeline_control.current_stage = "collection"

    rss_signals = collect_all_rss()
    pipeline_control.check_point()

    scraped_signals = collect_all_scraped()
    all_signals = rss_signals + scraped_signals

    new_count = 0
    reprocessed = 0
    for signal in all_signals:
        row_id = insert_signal(conn, signal)
        if row_id:
            new_count += 1
        else:
            # Signal already exists — reset to 'new' so it gets re-scored
            # with current thresholds and weights
            conn.execute(
                "UPDATE signals SET status = 'new' WHERE external_id = ?",
                (signal["external_id"],),
            )
            reprocessed += 1

    if reprocessed:
        conn.commit()

    total = new_count + reprocessed
    logger.info(
        "Collected %d signals (%d new, %d existing re-queued)",
        len(all_signals), new_count, reprocessed,
    )
    return total


def stage_validate(conn) -> int:
    """Stage 2: Validate new signals against 3+ sources."""
    logger.info("=== Stage 2: Validation ===")
    pipeline_control.current_stage = "validation"

    new_signals = get_signals_by_status(conn, "new")
    validated = 0

    for signal in new_signals:
        pipeline_control.check_point()
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
    pipeline_control.current_stage = "scoring"

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
        pipeline_control.check_point()
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

    # Cap the number of signals to keep the digest scannable
    max_signals = thresholds.get("max_signals_per_digest", 25)
    if len(scored_signals) > max_signals:
        logger.info(
            "Capping digest from %d to %d signals (top scores only)",
            len(scored_signals), max_signals,
        )
        scored_signals = scored_signals[:max_signals]

    ai_count = sum(1 for s in scored_signals if s.get("analysis_method", "").startswith("ai"))
    logger.info(
        "Scored %d signals (%d AI, %d heuristic), %d in digest",
        len(validated_signals), ai_count, len(validated_signals) - ai_count,
        len(scored_signals),
    )
    return scored_signals


def stage_compose(scored_signals: list[dict], pdf_mode: bool = False) -> tuple[str, str, dict, Path | None]:
    """Stage 5: Compose the HTML digest and optionally generate a PDF.

    Args:
        scored_signals: List of scored signal dicts.
        pdf_mode: If True, also generate a PDF version.

    Returns:
        Tuple of (html, subject, cid_images, pdf_path).
        pdf_path is None if pdf_mode is False.
    """
    logger.info("=== Stage 5: Composition ===")
    pipeline_control.current_stage = "composition"

    bu_config = get_business_units()
    context = build_digest_context(scored_signals, bu_config)

    html = render_digest(context)
    subject = context["subject"]
    cid_images = context.get("cid_images", {})

    # Always save a local copy
    save_digest_html(html, MOCK_OUTPUT_DIR)
    logger.info("Digest composed: %s (%d chars)", subject, len(html))

    # Generate PDF if requested
    pdf_path = None
    if pdf_mode:
        try:
            from src.composer.pdf_generator import generate_pdf
            pdf_path = generate_pdf(html, context, MOCK_OUTPUT_DIR, cid_images=cid_images)
            logger.info("PDF generated: %s (%d KB)", pdf_path, pdf_path.stat().st_size // 1024)
        except ImportError:
            logger.error(
                "PDF GENERATION SKIPPED: reportlab is not installed. "
                "Run 'pip install reportlab' to enable PDF delivery. "
                "Falling back to HTML-only email."
            )
        except Exception as e:
            logger.error(
                "PDF GENERATION FAILED: %s — falling back to HTML-only email. "
                "The digest will still be delivered as HTML.", e
            )

    return html, subject, cid_images, pdf_path


def stage_deliver(
    html: str, subject: str,
    cid_images: dict | None = None,
    pdf_path: Path | None = None,
) -> list[dict]:
    """Stage 6: Deliver the digest to recipients."""
    logger.info("=== Stage 6: Delivery (mode: %s) ===", DELIVERY_MODE)
    pipeline_control.current_stage = "delivery"

    recipients_config = get_recipients()
    results = []

    for recipient in recipients_config.get("recipients", []):
        if recipient.get("status") != "active":
            continue

        pipeline_control.check_point()

        result = send_email(
            to=recipient["email"],
            subject=subject,
            html_content=html,
            cid_images=cid_images,
            pdf_path=pdf_path,
        )
        results.append(result)
        logger.info("Delivery to %s: %s", recipient["email"], result["status"])

    sent = sum(1 for r in results if r["status"] == "sent")
    logger.info("Delivered to %d/%d recipients", sent, len(results))
    return results


def run_full_pipeline(pdf_mode: bool = False) -> dict:
    """Execute the complete 6-stage pipeline.

    Args:
        pdf_mode: If True, generate PDF and send as attachment.
    """
    setup_logging()
    pipeline_control.reset()
    logger.info("Starting VPG Intelligence Digest pipeline (pdf_mode=%s)", pdf_mode)

    conn = get_connection()
    init_db()

    run_id = insert_pipeline_run(conn, "full")

    try:
        # Stage 1: Collect
        collected = stage_collect(conn)
        pipeline_control.check_point()

        # Stage 2: Validate
        validated = stage_validate(conn)
        pipeline_control.check_point()

        # Stage 3-4: AI Score
        scored_signals = stage_score(conn)
        pipeline_control.check_point()

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
        pipeline_control.current_stage = "trends"
        trend_result = update_trends(conn)
        logger.info("Trends: %d updated, %d notable", trend_result["trends_updated"], len(trend_result["notable"]))
        pipeline_control.check_point()

        # Stage 5: Compose
        html, subject, cid_images, pdf_path = stage_compose(scored_signals, pdf_mode=pdf_mode)
        pipeline_control.check_point()

        # Stage 6: Deliver
        delivery_results = stage_deliver(html, subject, cid_images, pdf_path=pdf_path)

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
            "pdf_generated": pdf_path is not None,
        }

    except PipelineCancelled:
        logger.warning("Pipeline cancelled by user")
        complete_pipeline_run(conn, run_id, "cancelled", error_message="Cancelled by user")
        return {"status": "cancelled", "message": "Pipeline cancelled by user"}

    except Exception as e:
        logger.error("Pipeline failed: %s", str(e), exc_info=True)
        complete_pipeline_run(conn, run_id, "failed", error_message=str(e))
        return {"status": "failed", "error": str(e)}

    finally:
        pipeline_control.current_stage = ""
        conn.close()


if __name__ == "__main__":
    run_full_pipeline()
