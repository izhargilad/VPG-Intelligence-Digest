"""Tests for the delivery module (Gmail API + mock mode)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.delivery.auth import CREDENTIALS_PATH, TOKEN_PATH, check_auth_status
from src.delivery.gmail import (
    create_email_message,
    reset_service,
    send_email,
    send_gmail,
    send_mock,
)


# -- Mock mode tests --


class TestMockDelivery:
    def test_send_mock_creates_file(self, tmp_path):
        result = send_mock(
            to="user@example.com",
            subject="Test Subject",
            html_content="<h1>Hello</h1>",
            output_dir=tmp_path,
        )
        assert result["status"] == "sent"
        assert result["mode"] == "mock"
        assert result["recipient"] == "user@example.com"

        written = tmp_path / "digest_user_at_example_com.html"
        assert written.exists()
        assert "<h1>Hello</h1>" in written.read_text()

    def test_send_mock_sanitizes_email_in_filename(self, tmp_path):
        send_mock("a.b+c@sub.domain.org", "Subject", "<p>Hi</p>", tmp_path)
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert "@" not in files[0].name


# -- Email message creation --


class TestEmailMessage:
    def test_creates_multipart_message(self):
        msg = create_email_message(
            to="to@test.com",
            subject="Weekly Digest",
            html_content="<html><body>Hello</body></html>",
            sender="from@test.com",
        )
        assert msg["To"] == "to@test.com"
        assert msg["From"] == "from@test.com"
        assert msg["Subject"] == "Weekly Digest"

        # Should have 2 parts: plain text fallback + HTML
        payloads = msg.get_payload()
        assert len(payloads) == 2
        assert payloads[0].get_content_type() == "text/plain"
        assert payloads[1].get_content_type() == "text/html"


# -- Gmail API tests (mocked) --


class TestGmailDelivery:
    def setup_method(self):
        reset_service()

    def test_send_gmail_with_mocked_service(self):
        """Verify Gmail send works with a fully mocked API service."""
        mock_service = MagicMock()
        mock_send = mock_service.users().messages().send
        mock_send.return_value.execute.return_value = {"id": "msg-123abc"}

        with patch("src.delivery.gmail._get_gmail_service", return_value=mock_service):
            result = send_gmail("to@test.com", "Subject", "<p>Content</p>")

        assert result["status"] == "sent"
        assert result["mode"] == "gmail"
        assert result["gmail_message_id"] == "msg-123abc"
        assert result["recipient"] == "to@test.com"

    def test_send_email_mock_mode(self, tmp_path):
        """send_email in mock mode should write a file."""
        with patch("src.delivery.gmail.DELIVERY_MODE", "mock"), \
             patch("src.delivery.gmail.MOCK_OUTPUT_DIR", tmp_path):
            result = send_email("x@y.com", "Subject", "<p>Hi</p>")

        assert result["status"] == "sent"
        assert result["mode"] == "mock"

    def test_send_email_gmail_auth_missing_falls_back(self, tmp_path):
        """When Gmail auth is missing, send_email should fall back to mock."""
        with patch("src.delivery.gmail.DELIVERY_MODE", "gmail"), \
             patch("src.delivery.gmail.MOCK_OUTPUT_DIR", tmp_path), \
             patch("src.delivery.gmail._get_gmail_service", side_effect=RuntimeError("not authed")):
            result = send_email("x@y.com", "Subject", "<p>Hi</p>")

        assert result["status"] == "sent"
        assert result["mode"] == "mock"

    def test_send_email_retries_on_api_error(self):
        """Gmail API errors should retry with backoff."""
        mock_service = MagicMock()
        call_count = 0

        def failing_execute():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient API error")
            return {"id": "msg-retry-ok"}

        mock_service.users().messages().send.return_value.execute = failing_execute

        with patch("src.delivery.gmail.DELIVERY_MODE", "gmail"), \
             patch("src.delivery.gmail._get_gmail_service", return_value=mock_service), \
             patch("time.sleep"):  # Skip actual waits
            result = send_email("to@test.com", "Subject", "<p>Hi</p>", max_retries=3)

        assert result["status"] == "sent"
        assert call_count == 3

    def test_send_email_exhausts_retries(self):
        """After max retries, send_email should return failed."""
        mock_service = MagicMock()
        mock_service.users().messages().send.return_value.execute.side_effect = Exception("Permanent error")

        with patch("src.delivery.gmail.DELIVERY_MODE", "gmail"), \
             patch("src.delivery.gmail._get_gmail_service", return_value=mock_service), \
             patch("time.sleep"):
            result = send_email("to@test.com", "Subject", "<p>Hi</p>", max_retries=2)

        assert result["status"] == "failed"
        assert "Permanent error" in result["error"]


# -- Auth status tests --


class TestAuthStatus:
    def test_status_no_credentials(self, tmp_path):
        with patch("src.delivery.auth.CREDENTIALS_PATH", tmp_path / "nonexistent.json"):
            status = check_auth_status()
        assert not status["authorized"]
        assert "credentials.json" in status["message"]

    def test_status_not_authorized(self, tmp_path):
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text("{}")
        with patch("src.delivery.auth.CREDENTIALS_PATH", creds_path), \
             patch("src.delivery.auth.get_credentials", return_value=None):
            status = check_auth_status()
        assert not status["authorized"]

    def test_status_authorized(self, tmp_path):
        creds_path = tmp_path / "credentials.json"
        creds_path.write_text("{}")
        mock_creds = MagicMock()
        with patch("src.delivery.auth.CREDENTIALS_PATH", creds_path), \
             patch("src.delivery.auth.get_credentials", return_value=mock_creds):
            status = check_auth_status()
        assert status["authorized"]
