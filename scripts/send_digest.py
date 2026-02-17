"""Send the latest generated digest to all active recipients via SMTP.

Usage: python -m scripts.send_digest
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DELIVERY_MODE, MOCK_OUTPUT_DIR, get_recipients
from src.delivery.gmail import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    # Find latest digest
    digest_dir = MOCK_OUTPUT_DIR
    digests = sorted(digest_dir.glob("digest-*.html"))
    if not digests:
        logger.error("No digest HTML found in %s", digest_dir)
        sys.exit(1)

    digest_path = digests[-1]
    html_content = digest_path.read_text(encoding="utf-8")
    logger.info("Loaded digest: %s (%d chars)", digest_path.name, len(html_content))

    # Build subject from filename (digest-2026-W08.html -> Week 8)
    stem = digest_path.stem  # e.g. "digest-2026-W08"
    parts = stem.split("-")
    week = parts[-1] if len(parts) >= 3 else "W00"
    week_num = week.replace("W", "").lstrip("0") or "0"
    subject = f"VPG Intel [Week {week_num}]: Competitive Threats, Revenue Opportunities + 6 more signals"

    # Get active recipients
    recipients_config = get_recipients()
    active = [r for r in recipients_config.get("recipients", []) if r.get("status") == "active"]
    logger.info("Active recipients: %d", len(active))
    for r in active:
        logger.info("  -> %s (%s)", r["email"], r["name"])

    # Confirm delivery mode
    logger.info("Delivery mode: %s", DELIVERY_MODE)

    # Send
    results = []
    for recipient in active:
        logger.info("Sending to %s...", recipient["email"])
        result = send_email(
            to=recipient["email"],
            subject=subject,
            html_content=html_content,
        )
        results.append(result)
        logger.info("  Result: %s (mode: %s)", result["status"], result.get("mode", "unknown"))

    sent = sum(1 for r in results if r["status"] == "sent")
    logger.info("Sent %d/%d emails successfully", sent, len(results))

    if sent < len(results):
        failed = [r for r in results if r["status"] != "sent"]
        for f in failed:
            logger.error("  Failed: %s — %s", f.get("recipient"), f.get("error"))


if __name__ == "__main__":
    main()
