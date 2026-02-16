"""Gmail API delivery and mock file output for VPG Intelligence Digest.

Supports two modes:
- 'mock': Writes emails as local HTML files for preview
- 'gmail': Sends via Gmail API using OAuth2 credentials from config/token.json

First-time Gmail setup:
    1. Place credentials.json in config/
    2. Run: python -m src.delivery.auth
    3. Set DELIVERY_MODE=gmail in .env
"""

import base64
import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import DELIVERY_MODE, GMAIL_SENDER_EMAIL, MOCK_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Lazy-loaded Gmail API service
_gmail_service = None


def _get_gmail_service():
    """Get or create the authenticated Gmail API service client.

    Lazily initialized on first call. Reuses the same service for
    all sends within a pipeline run.
    """
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


def send_gmail(to: str, subject: str, html_content: str) -> dict:
    """Send email via the Gmail API.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: Rendered HTML body.

    Returns:
        Dict with 'status', 'mode', 'gmail_message_id', 'recipient'.
    """
    service = _get_gmail_service()
    msg = create_email_message(to, subject, html_content)

    # Gmail API requires base64url-encoded RFC 2822 message
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
    Falls back to mock mode if Gmail auth is missing.
    """
    mode = DELIVERY_MODE

    for attempt in range(max_retries):
        try:
            if mode == "mock":
                return send_mock(to, subject, html_content)

            if mode == "gmail":
                return send_gmail(to, subject, html_content)

            logger.error("Unknown delivery mode: %s", mode)
            return {"status": "failed", "error": f"Unknown mode: {mode}"}

        except RuntimeError as e:
            # Auth not configured — fall back to mock, don't retry
            logger.warning("Gmail auth unavailable, falling back to mock: %s", e)
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
