"""API authentication and rate limiting for VPG Intelligence Digest.

Provides:
- API key authentication via X-API-Key header
- Rate limiting per client IP
- Admin vs viewer role separation
"""

import hashlib
import logging
import os
import time
from collections import defaultdict
from functools import wraps

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# API key from environment (optional — disabled when not set)
API_KEY = os.getenv("VPG_API_KEY", "")
ADMIN_API_KEY = os.getenv("VPG_ADMIN_API_KEY", "")

# Rate limiting: max requests per minute per IP
RATE_LIMIT = int(os.getenv("VPG_RATE_LIMIT", "60"))
RATE_WINDOW = 60  # seconds

# In-memory rate tracking
_rate_tracker: dict[str, list[float]] = defaultdict(list)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _is_auth_enabled() -> bool:
    """Check if API authentication is enabled."""
    return bool(API_KEY or ADMIN_API_KEY)


def verify_api_key(api_key: str | None, require_admin: bool = False) -> bool:
    """Verify an API key. Returns True if valid or auth disabled."""
    if not _is_auth_enabled():
        return True
    if not api_key:
        return False
    if require_admin:
        return api_key == ADMIN_API_KEY
    return api_key in (API_KEY, ADMIN_API_KEY)


def check_rate_limit(client_ip: str) -> bool:
    """Check if a client IP is within rate limits. Returns True if allowed."""
    now = time.time()
    # Clean old entries
    _rate_tracker[client_ip] = [
        t for t in _rate_tracker[client_ip] if now - t < RATE_WINDOW
    ]
    if len(_rate_tracker[client_ip]) >= RATE_LIMIT:
        return False
    _rate_tracker[client_ip].append(now)
    return True


async def require_auth(request: Request, api_key: str | None = Security(api_key_header)):
    """FastAPI dependency for authenticated endpoints."""
    # Rate limiting always applies
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )

    # Auth check (skip if not configured)
    if _is_auth_enabled() and not verify_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header.",
        )


async def require_admin(request: Request, api_key: str | None = Security(api_key_header)):
    """FastAPI dependency for admin-only endpoints."""
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if _is_auth_enabled() and not verify_api_key(api_key, require_admin=True):
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
