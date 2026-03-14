"""Cron-based scheduling for VPG Intelligence Digest pipeline.

Provides automated weekly pipeline execution. Can be used standalone
or invoked via crontab/systemd timer.

Usage:
    # Run the pipeline immediately
    python -m src.scheduler --now

    # Install crontab entry for weekly Sunday 11 PM ET runs
    python -m src.scheduler --install

    # Remove crontab entry
    python -m src.scheduler --uninstall

    # Show current schedule
    python -m src.scheduler --status
"""

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CRON_TAG = "vpg-intelligence-digest"
# Default: Sunday 11 PM ET (Monday 4 AM UTC in summer, 3 AM in winter)
DEFAULT_CRON = "0 4 * * 1"  # Monday 4:00 AM UTC
DEFAULT_CRON_COMMENT = "VPG Intelligence Digest - Weekly pipeline run (Mon 4AM UTC / Sun 11PM ET)"


def run_pipeline_now(dry_run: bool = False, pdf_mode: bool = False):
    """Execute the full pipeline immediately."""
    from src.pipeline import run_full_pipeline

    logger.info("Starting scheduled pipeline run (dry_run=%s, pdf=%s)", dry_run, pdf_mode)
    start = datetime.now()

    try:
        result = run_full_pipeline(pdf_mode=pdf_mode)
        elapsed = (datetime.now() - start).total_seconds()
        logger.info("Pipeline completed in %.1f seconds: %s", elapsed, result.get("status", "unknown"))
        return result
    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()
        logger.error("Pipeline failed after %.1f seconds: %s", elapsed, e)
        raise


def get_crontab() -> str:
    """Get current crontab contents."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def install_cron(schedule: str = DEFAULT_CRON):
    """Install a crontab entry for the weekly pipeline run."""
    python = sys.executable
    script = str(PROJECT_ROOT / "src" / "scheduler.py")
    cron_line = f"{schedule} cd {PROJECT_ROOT} && {python} {script} --now >> {PROJECT_ROOT}/logs/scheduler.log 2>&1 # {CRON_TAG}"

    current = get_crontab()

    # Remove any existing VPG entries
    lines = [l for l in current.splitlines() if CRON_TAG not in l]
    lines.append(cron_line)

    new_crontab = "\n".join(lines) + "\n"

    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab, capture_output=True, text=True, timeout=10,
    )

    if proc.returncode == 0:
        print(f"Cron schedule installed: {schedule}")
        print(f"  {DEFAULT_CRON_COMMENT}")
        print(f"  Log: {PROJECT_ROOT}/logs/scheduler.log")
        return True
    else:
        print(f"Failed to install cron: {proc.stderr}")
        return False


def uninstall_cron():
    """Remove VPG Intelligence Digest crontab entries."""
    current = get_crontab()
    lines = [l for l in current.splitlines() if CRON_TAG not in l]
    new_crontab = "\n".join(lines) + "\n" if lines else ""

    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab, capture_output=True, text=True, timeout=10,
    )

    if proc.returncode == 0:
        print("VPG cron schedule removed.")
        return True
    else:
        print(f"Failed to uninstall cron: {proc.stderr}")
        return False


def get_schedule_status() -> dict:
    """Get current scheduling status."""
    current = get_crontab()
    vpg_entries = [l for l in current.splitlines() if CRON_TAG in l and not l.startswith("#")]

    return {
        "installed": len(vpg_entries) > 0,
        "entries": vpg_entries,
        "default_schedule": DEFAULT_CRON,
        "description": DEFAULT_CRON_COMMENT,
    }


def main():
    parser = argparse.ArgumentParser(description="VPG Intelligence Digest Scheduler")
    parser.add_argument("--now", action="store_true", help="Run pipeline immediately")
    parser.add_argument("--install", action="store_true", help="Install crontab entry")
    parser.add_argument("--uninstall", action="store_true", help="Remove crontab entry")
    parser.add_argument("--status", action="store_true", help="Show current schedule")
    parser.add_argument("--schedule", default=DEFAULT_CRON, help=f"Cron schedule (default: {DEFAULT_CRON})")
    parser.add_argument("--dry-run", action="store_true", help="Use seed data instead of live sources")
    parser.add_argument("--pdf", action="store_true", help="Generate PDF attachment")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.now:
        run_pipeline_now(dry_run=args.dry_run, pdf_mode=args.pdf)
    elif args.install:
        install_cron(args.schedule)
    elif args.uninstall:
        uninstall_cron()
    elif args.status:
        status = get_schedule_status()
        if status["installed"]:
            print("Schedule: ACTIVE")
            for entry in status["entries"]:
                print(f"  {entry}")
        else:
            print("Schedule: NOT INSTALLED")
            print(f"  Default: {status['default_schedule']} ({status['description']})")
            print(f"  Install with: python -m src.scheduler --install")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
