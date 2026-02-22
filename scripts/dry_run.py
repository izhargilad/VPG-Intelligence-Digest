"""Dry-run script: seeds the database with realistic signals, then
runs stages 2-6 of the VPG Intelligence Digest pipeline.

Used when live source collection is blocked (e.g. sandboxed environment).
Now delegates to the main pipeline's compose/deliver stages to ensure
PDF generation and inline-styled HTML are used consistently.
"""

import hashlib
import logging
import sys
from datetime import datetime

from src.analyzer.client import AnalysisClient
from src.analyzer.scorer import score_batch_ai, score_signal
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


# ── Realistic seed signals spanning multiple BUs ──────────────────────

SEED_SIGNALS = [
    {
        "title": "Kistler Launches Next-Gen Piezoelectric Force Sensor for Robotic Assembly Lines",
        "summary": (
            "Kistler has announced its new 9175B piezoelectric force sensor designed "
            "specifically for collaborative robot (cobot) end-effectors. The sensor offers "
            "±0.1% linearity and an integrated digital interface, targeting the growing "
            "cobot market expected to reach $12B by 2028. The launch directly competes "
            "with VPG Force Sensors' load cell product line for robotic integration."
        ),
        "url": "https://www.kistler.com/en/newsroom/piezo-9175b-launch",
        "source_id": "kistler-news",
        "source_name": "Kistler Newsroom",
        "source_tier": 1,
        "published_at": "2026-02-14T10:00:00",
    },
    {
        "title": "Caterpillar Expanding Autonomous Mining Fleet, Seeking New Onboard Weighing Partners",
        "summary": (
            "Caterpillar's Mining & Technology division has issued an RFI for integrated "
            "onboard weighing systems across its 794 AC autonomous haul truck fleet. The "
            "program covers 200+ vehicles at three Australian mine sites, with partner "
            "selection expected by Q3 2026. This represents a major revenue opportunity "
            "for VPG Onboard Weighing's TruckWeigh and BulkWeigh product lines."
        ),
        "url": "https://www.caterpillar.com/en/news/2026/autonomous-mining-expansion.html",
        "source_id": "cat-news",
        "source_name": "Caterpillar News",
        "source_tier": 1,
        "published_at": "2026-02-13T14:30:00",
    },
    {
        "title": "HBK Acquires Strain Gage Startup, Expands into Structural Health Monitoring",
        "summary": (
            "Hottinger Brüel & Kjær (HBK) has acquired StrainSense Labs, a UK-based "
            "startup specializing in wireless strain gage networks for bridge and building "
            "monitoring. The acquisition strengthens HBK's position against Micro-Measurements "
            "in the structural testing market and signals a push into IoT-connected SHM. "
            "The deal was reportedly valued at €45M."
        ),
        "url": "https://www.hbkworld.com/en/news/hbk-strainsense-acquisition",
        "source_id": "hbk-news",
        "source_name": "HBK Press Releases",
        "source_tier": 1,
        "published_at": "2026-02-12T09:00:00",
    },
    {
        "title": "US Raises Tariffs on Chinese Electronic Components to 50%, India Exempted",
        "summary": (
            "The Office of the US Trade Representative announced a new tariff schedule "
            "raising duties on Chinese-origin electronic components — including resistors, "
            "sensors, and data acquisition modules — from 25% to 50%, effective April 1, 2026. "
            "India, Vietnam, and Mexico are explicitly exempted. This benefits VPG's India "
            "manufacturing hub and creates competitive pressure on China-dependent rivals "
            "like Zemic and Sunrise Instruments."
        ),
        "url": "https://ustr.gov/tariff-update-2026-electronics",
        "source_id": "ustr-press",
        "source_name": "USTR Press Releases",
        "source_tier": 1,
        "published_at": "2026-02-11T16:00:00",
    },
    {
        "title": "Figure AI Places $30M Order for Miniature Force/Torque Sensors for Humanoid Robots",
        "summary": (
            "Humanoid robotics company Figure AI has placed a large-scale order for "
            "miniature 6-axis force/torque sensors to be integrated into the hands and "
            "wrists of its Figure 02 humanoid robot platform. The order, reportedly worth "
            "$30M over 18 months, is one of the largest single sensor procurements in "
            "the robotics industry. The supplier was not disclosed, presenting both a "
            "competitive threat and partnership opportunity for VPG Force Sensors."
        ),
        "url": "https://www.figure.ai/blog/sensor-procurement-2026",
        "source_id": "figure-ai",
        "source_name": "Figure AI Blog",
        "source_tier": 2,
        "published_at": "2026-02-10T12:00:00",
    },
    {
        "title": "ArcelorMittal Invests $2B in Smart Steel Mill Upgrades with Laser Measurement Systems",
        "summary": (
            "ArcelorMittal has announced a global modernization program investing $2B in "
            "AI-driven quality control for its flat steel rolling mills across Europe and "
            "North America. The program includes real-time laser thickness and profile "
            "measurement — the exact application space of KELK's rolling mill systems and "
            "Nokra's laser measurement technology. Multiple vendors are in early-stage trials."
        ),
        "url": "https://corporate.arcelormittal.com/media/press-releases/smart-mill-2026",
        "source_id": "metalminer",
        "source_name": "MetalMiner",
        "source_tier": 1,
        "published_at": "2026-02-09T08:00:00",
    },
    {
        "title": "Humanetics Selects New DAQ Partner for Next-Gen Crash Test Dummies",
        "summary": (
            "Humanetics, the world's largest crash test dummy manufacturer and a key VPG "
            "target account, is evaluating data acquisition systems for its upcoming THOR-50M "
            "Gen 3 dummy. The requirements call for 256+ channels of miniaturized, shock-rated "
            "DAQ capable of surviving 150g impacts. This is a direct fit for DTS miniature "
            "data acquisition and Pacific Instruments high-performance DAQ capabilities."
        ),
        "url": "https://www.humanetics.com/news/daq-partner-search-2026",
        "source_id": "sae-news",
        "source_name": "SAE International",
        "source_tier": 1,
        "published_at": "2026-02-08T11:00:00",
    },
    {
        "title": "Semiconductor Test Equipment Market Surges 18% — Precision Resistor Demand Spikes",
        "summary": (
            "The global semiconductor automated test equipment (ATE) market grew 18% "
            "year-over-year in Q4 2025, driven by AI chip testing demand. ATE manufacturers "
            "are reporting supply constraints on ultra-precision foil resistors used in "
            "test measurement circuits. This creates a strong demand signal for VPG Foil "
            "Resistors' Z1-Foil product line, which targets this exact application."
        ),
        "url": "https://www.eetimes.com/semiconductor-test-market-2026-outlook",
        "source_id": "ee-times",
        "source_name": "EE Times",
        "source_tier": 1,
        "published_at": "2026-02-07T15:00:00",
    },
]


def _make_external_id(signal: dict) -> str:
    """Generate a dedup hash matching the collector format."""
    raw = f"{signal['url']}:{signal['title']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def seed_signals(conn) -> int:
    """Insert seed signals into the database. Returns count inserted.

    On re-runs, resets existing seed signals back to 'new' status so the
    pipeline can reprocess them.
    """
    inserted = 0
    for sig in SEED_SIGNALS:
        sig["external_id"] = _make_external_id(sig)
        row_id = insert_signal(conn, sig)
        if row_id:
            inserted += 1
        else:
            # Signal already exists — reset to 'new' so it gets reprocessed
            conn.execute(
                "UPDATE signals SET status = 'new' WHERE external_id = ?",
                (sig["external_id"],),
            )
            inserted += 1
    conn.commit()
    return inserted


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"dryrun_{timestamp}.log"
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main(pdf_mode: bool = True):
    """Run the dry-run pipeline.

    Args:
        pdf_mode: If True (default), generate a PDF and send as attachment.
                  This bypasses enterprise spam filters that scramble HTML.
    """
    setup_logging()
    logger.info("=== VPG Intelligence Digest — Dry Run (pdf_mode=%s) ===", pdf_mode)

    conn = get_connection()
    init_db()
    run_id = insert_pipeline_run(conn, "dry-run")

    try:
        # Stage 1: Seed instead of live collection
        logger.info("=== Stage 1: Seeding %d signals ===", len(SEED_SIGNALS))
        inserted = seed_signals(conn)
        logger.info("Seeded %d signals (%d new)", len(SEED_SIGNALS), inserted)

        # Stage 2: Validation
        logger.info("=== Stage 2: Validation ===")
        new_signals = get_signals_by_status(conn, "new")
        for signal in new_signals:
            validate_signal(conn, signal)
            update_signal_status(conn, signal["id"], "validated")
        logger.info("Validated %d signals", len(new_signals))

        # Stage 3-4: AI Scoring
        logger.info("=== Stage 3-4: AI Scoring & Analysis ===")
        validated_signals = get_signals_by_status(conn, "validated")
        if not validated_signals:
            logger.warning("No validated signals to score")
            complete_pipeline_run(
                conn, run_id, "completed",
                signals_collected=inserted,
                signals_validated=len(new_signals),
                signals_scored=0,
            )
            return

        client = AnalysisClient()
        if client.available:
            logger.info("Anthropic API available — using AI scoring")
        else:
            logger.warning("Anthropic API unavailable — using heuristic fallback")

        thresholds = get_scoring_weights().get("thresholds", {})
        min_score = thresholds.get("include_in_digest", 4.0)

        scored_signals = []
        AI_BATCH_SIZE = 10
        for i in range(0, len(validated_signals), AI_BATCH_SIZE):
            batch = validated_signals[i:i + AI_BATCH_SIZE]
            if client.available and len(batch) > 1:
                results = score_batch_ai(batch, client)
            else:
                results = [score_signal(s, client) for s in batch]

            for signal, analysis in zip(batch, results):
                signal.update(analysis)
                signal["composite_score"] = analysis["composite"]
                insert_analysis(conn, signal["id"], analysis)
                save_signal_bus(conn, signal["id"], analysis.get("bu_matches", []))
                update_signal_status(conn, signal["id"], "scored")
                if analysis["composite"] >= min_score:
                    scored_signals.append(signal)

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

        if not scored_signals:
            logger.warning("No signals above threshold for digest")
            complete_pipeline_run(
                conn, run_id, "completed",
                signals_collected=inserted,
                signals_validated=len(new_signals),
                signals_scored=0,
            )
            return

        # Trend analysis
        logger.info("=== Trend Analysis ===")
        trend_result = update_trends(conn)
        logger.info("Trends: %d updated, %d notable",
                     trend_result["trends_updated"], len(trend_result["notable"]))

        # Stage 5: Composition (use main pipeline's compose which supports PDF)
        logger.info("=== Stage 5: Composition ===")
        bu_config = get_business_units()
        context = build_digest_context(scored_signals, bu_config)
        html = render_digest(context)
        subject = context["subject"]
        cid_images = context.get("cid_images", {})
        saved_path = save_digest_html(html, MOCK_OUTPUT_DIR)
        logger.info("Digest composed: %s (%d chars)", subject, len(html))

        # Generate PDF if requested
        pdf_path = None
        if pdf_mode:
            try:
                from src.composer.pdf_generator import generate_pdf
                pdf_path = generate_pdf(
                    html, context, MOCK_OUTPUT_DIR, cid_images=cid_images
                )
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

        # Stage 6: Delivery
        logger.info("=== Stage 6: Delivery (mode: %s, pdf: %s) ===",
                     DELIVERY_MODE, pdf_path is not None)
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
                pdf_path=pdf_path,
            )
            results.append(result)
            logger.info("Delivery to %s: %s", recipient["email"], result["status"])

        sent = sum(1 for r in results if r["status"] == "sent")
        logger.info("Delivered to %d/%d recipients", sent, len(results))

        complete_pipeline_run(
            conn, run_id, "completed",
            signals_collected=inserted,
            signals_validated=len(new_signals),
            signals_scored=len(scored_signals),
        )

        logger.info("=== Dry Run Complete ===")
        logger.info("Output file: %s", saved_path)
        if pdf_path:
            logger.info("PDF file: %s", pdf_path)
            print(f"\nPDF digest saved to: {pdf_path}")
        print(f"HTML digest saved to: {saved_path}")

    except Exception as e:
        logger.error("Dry run failed: %s", str(e), exc_info=True)
        complete_pipeline_run(conn, run_id, "failed", error_message=str(e))
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
