"""Gmail API delivery and mock file output for VPG Intelligence Digest.

Supports two modes:
- 'mock': Writes emails as local HTML files for preview
- 'gmail': Sends via Gmail API (requires OAuth2 credentials)
"""

import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import (
    DELIVERY_MODE,
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN,
    GMAIL_SENDER_EMAIL,
    MOCK_OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def create_email_message(
    to: str, subject: str, html_content: str, sender: str | None = None
) -> MIMEMultipart:
    """Create a MIME email message."""
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = sender or GMAIL_SENDER_EMAIL
    msg["Subject"] = subject

    plain_text = "This email requires an HTML-capable email client."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    return msg


def send_mock(
    to: str, subject: str, html_content: str, output_dir: Path | None = None
) -> dict:
    """Save email as local HTML file (mock mode)."""
    out = output_dir or MOCK_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    safe_to = to.replace("@", "_at_").replace(".", "_")
    filename = f"digest_{safe_to}.html"
    path = out / filename

    path.write_text(html_content, encoding="utf-8")
    logger.info("Mock email saved: %s -> %s", to, path)

    return {
        "status": "sent",
        "mode": "mock",
        "file_path": str(path),
        "recipient": to,
    }


def send_gmail(to: str, subject: str, html_content: str) -> dict:
    """Send email via Gmail API.

    Will be fully implemented when Gmail API credentials are provided.
    """
    if not all([GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN]):
        logger.warning("Gmail API credentials not configured. Falling back to mock mode.")
        return send_mock(to, subject, html_content)

    # TODO: Implement Gmail API send with OAuth2 in Phase 1 continuation
    logger.error("Gmail API send not yet implemented")
    return {
        "status": "failed",
        "mode": "gmail",
        "error": "Gmail API not yet implemented",
        "recipient": to,
    }


def send_email(
    to: str, subject: str, html_content: str, max_retries: int = 3
) -> dict:
    """Send an email using the configured delivery mode with retry logic."""
    mode = DELIVERY_MODE

    for attempt in range(max_retries):
        try:
            if mode == "mock":
                return send_mock(to, subject, html_content)
            elif mode == "gmail":
                result = send_gmail(to, subject, html_content)
                if result["status"] == "sent":
                    return result
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Retry %d/%d in %ds", attempt + 1, max_retries, wait)
                    time.sleep(wait)
            else:
                logger.error("Unknown delivery mode: %s", mode)
                return {"status": "failed", "error": f"Unknown mode: {mode}"}

        except Exception as e:
            logger.error("Delivery attempt %d failed: %s", attempt + 1, str(e))
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                return {
                    "status": "failed",
                    "mode": mode,
                    "error": str(e),
                    "recipient": to,
                }

    return {"status": "failed", "mode": mode, "recipient": to}
