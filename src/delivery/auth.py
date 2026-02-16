"""Gmail OAuth2 authentication for VPG Intelligence Digest.

Handles the initial authorization flow and token refresh lifecycle.

Usage (first-time setup):
    python -m src.delivery.auth

This opens a browser for Google account authorization, then saves the
refresh token to config/token.json for all future API calls.
"""

import json
import logging
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import CONFIG_DIR

logger = logging.getLogger(__name__)

# Gmail API scopes — send-only (least privilege)
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def get_credentials() -> Credentials | None:
    """Load or refresh Gmail API credentials.

    Returns valid credentials from the stored token, refreshing if expired.
    Returns None if no token exists (needs initial authorization).
    """
    if not TOKEN_PATH.exists():
        logger.info("No token.json found — run 'python -m src.delivery.auth' to authorize")
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            logger.info("Gmail token refreshed successfully")
            return creds
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return None

    logger.warning("Stored token is invalid and cannot be refreshed")
    return None


def _save_token(creds: Credentials) -> None:
    """Persist credentials to token.json."""
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
    logger.info("Token saved to %s", TOKEN_PATH)


def run_auth_flow() -> Credentials:
    """Run the interactive OAuth2 authorization flow.

    Opens a local browser window for the user to authorize Gmail access.
    Saves the resulting token to config/token.json.

    Returns:
        Authorized Credentials object.

    Raises:
        FileNotFoundError: If credentials.json is missing.
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Gmail credentials not found at {CREDENTIALS_PATH}\n"
            "Download OAuth2 credentials from Google Cloud Console and save as:\n"
            f"  {CREDENTIALS_PATH}"
        )

    print("=" * 60)
    print("VPG Intelligence Digest — Gmail Authorization")
    print("=" * 60)
    print()
    print("A browser window will open for Google account authorization.")
    print("Grant 'Send email' permission to enable digest delivery.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH), SCOPES
    )

    # run_local_server handles the redirect and token exchange
    creds = flow.run_local_server(
        port=8090,
        prompt="consent",
        access_type="offline",
    )

    _save_token(creds)

    print()
    print("Authorization successful!")
    print(f"Token saved to: {TOKEN_PATH}")
    print("The digest pipeline can now send emails via Gmail.")
    print("=" * 60)

    return creds


def check_auth_status() -> dict:
    """Check the current Gmail authentication status.

    Returns:
        Dict with 'authorized', 'email' (if available), and 'message'.
    """
    if not CREDENTIALS_PATH.exists():
        return {
            "authorized": False,
            "message": "credentials.json not found in config/",
        }

    creds = get_credentials()
    if creds is None:
        return {
            "authorized": False,
            "credentials_found": True,
            "message": "Not authorized — run 'python -m src.delivery.auth'",
        }

    return {
        "authorized": True,
        "message": "Gmail API authorized and ready",
    }


# Allow running as: python -m src.delivery.auth
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    status = check_auth_status()
    if status["authorized"]:
        print("Already authorized. Re-authorizing...")

    try:
        run_auth_flow()
    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAuthorization failed: {e}", file=sys.stderr)
        sys.exit(1)
