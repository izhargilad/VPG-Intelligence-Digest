"""Automated weekly scheduler for VPG Intelligence Digest.

Runs the full pipeline on a configurable schedule (default: Monday 7:00 AM ET).

Usage:
    # Run as a persistent service
    python -m scripts.scheduler

    # Or register with Windows Task Scheduler / cron:
    #   Windows: schtasks /create /tn "VPG Digest" /tr "python -m scripts.scheduler --once" /sc weekly /d MON /st 07:00
    #   Linux:   0 7 * * 1 cd /path/to/VPG-Intelligence-Digest && python -m scripts.scheduler --once >> logs/cron.log 2>&1

Options:
    --once       Run the pipeline once and exit (for Task Scheduler / cron)
    --dry-run    Run with seed data instead of live collection
"""

import argparse
import logging
import sys
import time
from datetime import datetime

import schedule

from src.config import LOGS_DIR, get_recipients

logger = logging.getLogger(__name__)


def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"scheduler_{timestamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_pipeline():
    """Execute the full pipeline."""
    logger.info("=== Scheduled pipeline run starting ===")
    try:
        from src.pipeline import run_full_pipeline
        result = run_full_pipeline()
        logger.info("Pipeline completed: %s", result.get("status"))
        return result
    except Exception as e:
        logger.error("Scheduled pipeline run failed: %s", str(e), exc_info=True)
        return {"status": "failed", "error": str(e)}


def run_dry_run():
    """Execute the dry-run pipeline with seed data."""
    logger.info("=== Scheduled dry-run starting ===")
    try:
        from scripts.dry_run import main as dry_run_main
        dry_run_main()
        return {"status": "completed"}
    except Exception as e:
        logger.error("Scheduled dry-run failed: %s", str(e), exc_info=True)
        return {"status": "failed", "error": str(e)}


def start_scheduler(dry_run: bool = False):
    """Start the persistent scheduler that runs weekly.

    Reads the schedule from recipients.json delivery_settings.
    """
    recipients = get_recipients()
    settings = recipients.get("delivery_settings", {})
    send_day = settings.get("send_day", "monday").lower()
    send_time = settings.get("send_time_et", "07:00")

    job_fn = run_dry_run if dry_run else run_pipeline

    # Map day names to schedule methods
    day_map = {
        "monday": schedule.every().monday,
        "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday,
        "thursday": schedule.every().thursday,
        "friday": schedule.every().friday,
        "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }

    scheduler_fn = day_map.get(send_day, schedule.every().monday)
    scheduler_fn.at(send_time).do(job_fn)

    mode = "dry-run" if dry_run else "live"
    logger.info(
        "Scheduler started (%s mode): runs every %s at %s",
        mode, send_day.capitalize(), send_time,
    )
    logger.info("Next run: %s", schedule.next_run())
    print(f"\nScheduler running ({mode} mode) — {send_day.capitalize()} at {send_time}")
    print(f"Next run: {schedule.next_run()}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        print("\nScheduler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="VPG Intelligence Digest Scheduler"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run the pipeline once and exit (for cron / Task Scheduler)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use seed data instead of live collection",
    )
    args = parser.parse_args()

    setup_logging()

    if args.once:
        result = run_dry_run() if args.dry_run else run_pipeline()
        sys.exit(0 if result.get("status") == "completed" else 1)
    else:
        start_scheduler(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
