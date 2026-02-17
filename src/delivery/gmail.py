"""Email delivery for VPG Intelligence Digest.

Supports three modes:
- 'mock': Writes emails as local HTML files for preview
- 'smtp': Sends via Gmail SMTP with App Password (recommended — simplest setup)
- 'gmail': Sends via Gmail API using OAuth2 credentials

SMTP setup (recommended):
    1. Enable 2-Step Verification on your Google Account
    2. Go to https://myaccount.google.com/apppasswords
    3. Generate an App Password for "Mail"
    4. Set GMAIL_SENDER_EMAIL and GMAIL_APP_PASSWORD in .env
    5. Set DELIVERY_MODE=smtp
"""

import base64
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import (
    DELIVERY_MODE,
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER_EMAIL,
    MOCK_OUTPUT_DIR,
)

logger = logging.getLogger(__name__)

# Lazy-loaded Gmail API service (only for 'gmail' OAuth2 mode)
_gmail_service = None


def create_email_message(
    to: str, subject: str, html_content: str, sender: str | None = None
) -> MIMEMultipart:
    """Create a MIME email message with HTML body and plain-text fallback."""
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


def send_smtp(to: str, subject: str, html_content: str) -> dict:
    """Send email via Gmail SMTP with App Password.

    Requires GMAIL_SENDER_EMAIL and GMAIL_APP_PASSWORD in .env.
    No OAuth2, no credentials.json, no browser auth needed.
    """
    if not GMAIL_SENDER_EMAIL:
        raise RuntimeError("GMAIL_SENDER_EMAIL not set in .env")
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD not set in .env. "
            "Generate one at https://myaccount.google.com/apppasswords"
        )

    msg = create_email_message(to, subject, html_content)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    logger.info("SMTP email sent to %s from %s", to, GMAIL_SENDER_EMAIL)

    return {
        "status": "sent",
        "mode": "smtp",
        "recipient": to,
    }


def _get_gmail_service():
    """Get or create the authenticated Gmail API service client (OAuth2 mode)."""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    from googleapiclient.discovery import build

    from src.delivery.auth import get_credentials

    creds = get_credentials()
    if creds is None:
        raise RuntimeError(
            "Gmail not authorized. Run 'python -m src.delivery.auth' first."
        )

    _gmail_service = build("gmail", "v1", credentials=creds)
    logger.info("Gmail API service initialized")
    return _gmail_service


def send_gmail(to: str, subject: str, html_content: str) -> dict:
    """Send email via the Gmail API (OAuth2 mode)."""
    service = _get_gmail_service()
    msg = create_email_message(to, subject, html_content)

    raw_bytes = msg.as_bytes()
    encoded = base64.urlsafe_b64encode(raw_bytes).decode("ascii")

    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": encoded})
        .execute()
    )

    message_id = result.get("id", "")
    logger.info("Gmail sent to %s (message_id: %s)", to, message_id)

    return {
        "status": "sent",
        "mode": "gmail",
        "gmail_message_id": message_id,
        "recipient": to,
    }


def send_email(
    to: str, subject: str, html_content: str, max_retries: int = 3
) -> dict:
    """Send an email using the configured delivery mode with retry logic.

    Retries with exponential backoff on transient failures.
    Falls back to mock mode if auth is missing.
    """
    mode = DELIVERY_MODE

    for attempt in range(max_retries):
        try:
            if mode == "mock":
                return send_mock(to, subject, html_content)

            if mode == "smtp":
                return send_smtp(to, subject, html_content)

            if mode == "gmail":
                return send_gmail(to, subject, html_content)

            logger.error("Unknown delivery mode: %s", mode)
            return {"status": "failed", "error": f"Unknown mode: {mode}"}

        except RuntimeError as e:
            # Auth not configured — fall back to mock, don't retry
            logger.warning("Auth unavailable, falling back to mock: %s", e)
            return send_mock(to, subject, html_content)

        except Exception as e:
            logger.error("Delivery attempt %d/%d failed: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.info("Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                return {
                    "status": "failed",
                    "mode": mode,
                    "error": str(e),
                    "recipient": to,
                }

    return {"status": "failed", "mode": mode, "recipient": to}


def reset_service() -> None:
    """Reset the cached Gmail service (useful for testing or re-auth)."""
    global _gmail_service
    _gmail_service = None
