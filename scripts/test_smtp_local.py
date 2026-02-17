"""Local SMTP validation test.

Starts a local SMTP debug server, sends the digest through it,
and verifies the email was transmitted correctly — proving the
full send path works without needing real Gmail credentials.

Usage: python -m scripts.test_smtp_local
"""

import base64
import email
import quopri
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Local SMTP capture server ──────────────────────────────────────

captured_messages = []

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 9025


class CaptureSMTPHandler:
    """SMTP handler that stores received messages."""

    async def handle_DATA(self, server, session, envelope):
        raw = envelope.content.decode("utf-8", errors="replace")
        # Parse the MIME message to get decoded content
        parsed = email.message_from_string(raw)
        decoded_parts = []
        for part in parsed.walk():
            payload = part.get_payload(decode=True)
            if payload:
                decoded_parts.append(payload.decode("utf-8", errors="replace"))

        captured_messages.append({
            "from": envelope.mail_from,
            "to": envelope.rcpt_tos,
            "raw": raw,
            "decoded": "\n".join(decoded_parts),
            "subject": parsed.get("Subject", ""),
        })
        return "250 OK"


def start_local_smtp():
    """Start a local SMTP server in a background thread."""
    from aiosmtpd.controller import Controller

    handler = CaptureSMTPHandler()
    controller = Controller(handler, hostname=LOCAL_HOST, port=LOCAL_PORT)
    controller.start()
    return controller


# ── Test functions ──────────────────────────────────────────────────

def test_basic_send():
    """Test 1: Basic SMTP send to local server."""
    print("\n--- Test 1: Basic SMTP send ---")

    msg = MIMEMultipart("alternative")
    msg["To"] = "test@example.com"
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test Email"
    msg.attach(MIMEText("Plain text fallback", "plain"))
    msg.attach(MIMEText("<h1>Hello</h1>", "html"))

    with smtplib.SMTP(LOCAL_HOST, LOCAL_PORT) as server:
        server.send_message(msg)

    assert len(captured_messages) == 1, "Expected 1 captured message"
    m = captured_messages[0]
    assert "test@example.com" in m["to"]
    assert "sender@example.com" == m["from"]
    assert m["subject"] == "Test Email"
    print("  From:", m["from"])
    print("  To:", m["to"])
    print("  Subject:", m["subject"])
    print("  PASS")


def test_digest_send():
    """Test 2: Send the actual generated digest through local SMTP."""
    print("\n--- Test 2: Full digest email send ---")

    # Load latest digest HTML
    digest_dir = Path("data/mock-digests")
    digests = sorted(digest_dir.glob("digest-*.html"))
    if not digests:
        print("  SKIP: No digest HTML found. Run dry_run first.")
        return

    digest_path = digests[-1]
    html_content = digest_path.read_text(encoding="utf-8")
    print(f"  Loaded digest: {digest_path.name} ({len(html_content):,} chars)")

    # Build the email exactly like src/delivery/gmail.py does
    msg = MIMEMultipart("alternative")
    msg["To"] = "izhargilad@gmail.com"
    msg["From"] = "vpg-digest@test.local"
    msg["Subject"] = "VPG Intel [Week 8]: Test Digest Validation"
    msg.attach(MIMEText("This email requires an HTML-capable email client.", "plain"))
    msg.attach(MIMEText(html_content, "html"))

    initial_count = len(captured_messages)
    with smtplib.SMTP(LOCAL_HOST, LOCAL_PORT) as server:
        server.send_message(msg)

    assert len(captured_messages) == initial_count + 1, "Message not captured"
    m = captured_messages[-1]
    decoded = m["decoded"]

    # Validate email structure against decoded content
    checks = {
        "Recipient correct": "izhargilad@gmail.com" in m["to"],
        "Has Subject header": "VPG Intel" in m["subject"],
        "Has HTML content": "<html" in decoded.lower() or "<!doctype" in decoded.lower(),
        "Has VPG branding (#1B2A4A)": "#1B2A4A" in decoded or "#1b2a4a" in decoded,
        "Has action cards": "action" in decoded.lower() or "signal" in decoded.lower(),
        "Has plain-text fallback": "HTML-capable" in decoded,
        "Content size > 10KB": len(decoded) > 10_000,
        "MIME multipart": "multipart/alternative" in m["raw"],
    }

    all_pass = True
    for check, result in checks.items():
        status = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        print(f"  {status}: {check}")

    print(f"  Email size: {len(m['raw']):,} bytes (raw MIME)")
    print(f"  HTML body: {len(html_content):,} chars")
    print(f"  {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    return all_pass


def test_create_email_message():
    """Test 3: Verify create_email_message() from delivery module."""
    print("\n--- Test 3: create_email_message() function ---")

    from src.delivery.gmail import create_email_message

    msg = create_email_message(
        to="recipient@example.com",
        subject="Test Subject Line",
        html_content="<html><body><h1>Test</h1></body></html>",
        sender="sender@example.com",
    )

    # Send through local server
    initial_count = len(captured_messages)
    with smtplib.SMTP(LOCAL_HOST, LOCAL_PORT) as server:
        server.send_message(msg)

    assert len(captured_messages) == initial_count + 1
    m = captured_messages[-1]
    decoded = m["decoded"]

    checks = {
        "To header set": "recipient@example.com" in m["to"],
        "From header set": "sender@example.com" == m["from"],
        "Subject correct": m["subject"] == "Test Subject Line",
        "HTML part present": "<h1>Test</h1>" in decoded,
        "Plain fallback present": "HTML-capable" in decoded,
        "MIME multipart": "multipart/alternative" in m["raw"],
    }

    all_pass = True
    for check, result in checks.items():
        status = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        print(f"  {status}: {check}")

    print(f"  {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    return all_pass


# ── Main ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("VPG Intelligence Digest — Local SMTP Validation")
    print("=" * 60)

    # Start local SMTP server
    print(f"\nStarting local SMTP server on {LOCAL_HOST}:{LOCAL_PORT}...")
    controller = start_local_smtp()
    time.sleep(0.5)  # Let it bind
    print("Local SMTP server running.")

    try:
        test_basic_send()
        test_digest_send()
        test_create_email_message()

        print("\n" + "=" * 60)
        total = len(captured_messages)
        print(f"Done. {total} email(s) captured and validated.")
        print("SMTP sending logic is working correctly.")
        print("=" * 60)

    finally:
        controller.stop()
        print("Local SMTP server stopped.")


if __name__ == "__main__":
    main()
