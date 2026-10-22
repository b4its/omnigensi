"""Password-based authentication for a single-operator deployment.

Design constraints, deliberately simple:

* One shared password (``APP_PASSWORD``, default ``"123"``) protects the
  whole instance. There are no users or roles.
* A successful login returns a signed, expiring token. It is delivered as an
  httpOnly cookie (works for the web UI and WebViews) **and** in the response
  body so native mobile clients can send ``Authorization: Bearer``.
* ``EventSource`` cannot set headers, so the SSE endpoint additionally accepts
  ``?token=``.

The token is ``base64(payload).hmac`` where the payload carries an issued-at
and expiry timestamp. The HMAC is verified with a constant-time comparison so
an attacker cannot learn the signature byte by byte.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("omnigensi.auth")

# Endpoints reachable without a session.
PUBLIC_PATHS: Tuple[str, ...] = (
    "/health",
    "/api/v1/health",
    "/api/v1/config",
    "/api/v1/auth/login",
    "/api/v1/auth/session",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _secret() -> bytes:
    raw = settings.AUTH_TOKEN_SECRET or settings.ENCRYPTION_KEY
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign_payload(payload: Dict[str, object]) -> Tuple[str, int]:
    """Signs a JSON payload and returns (token, expiry)."""
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(
        hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}", int(payload["exp"])  # type: ignore[arg-type]


def issue_token(ttl_seconds: Optional[int] = None) -> Tuple[str, int]:
    """Creates a signed session token.

    Returns the token and its expiry as a unix timestamp.
    """
    ttl = settings.AUTH_TOKEN_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now = int(time.time())
    expires_at = now + ttl
    payload = {"iat": now, "exp": expires_at, "scope": "session", "nonce": secrets.token_hex(8)}
    return _sign_payload(payload)


def issue_stream_ticket(ttl_seconds: int = 120) -> Tuple[str, int]:
    """Creates a short-lived ticket for URL-based auth.

    ``EventSource`` and ``<a download>`` cannot set headers, so the credential
    has to travel in the query string. Sending the 7-day session token there
    would leak it into access logs, proxy logs and Referer headers, so clients
    exchange it for a ticket that expires in minutes and is scoped by a marker
    inside the signed payload.
    """
    ttl = max(30, min(ttl_seconds, 900))
    now = int(time.time())
    expires_at = now + ttl
    payload = {"iat": now, "exp": expires_at, "scope": "stream", "nonce": secrets.token_hex(8)}
    return _sign_payload(payload)


def verify_token(token: Optional[str], required_scope: Optional[str] = None) -> bool:
    """Validates signature, expiry and scope. Never raises."""
    if not token or "." not in token:
        return False
    encoded, _, signature = token.partition(".")
    if not encoded or not signature:
        return False

    expected = _b64encode(
        hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, signature):
        return False

    try:
        payload: Dict[str, Any] = json.loads(_b64decode(encoded))
    except (ValueError, json.JSONDecodeError):
        return False

    try:
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError):
        return False

    if expires_at <= int(time.time()):
        return False

    # A stream ticket must not be usable as a full session, and vice versa.
    scope = payload.get("scope") or "session"
    if required_scope is not None and scope != required_scope:
        return False
    if required_scope is None and scope != "session":
        return False

    return True


def password_matches(candidate: Optional[str]) -> bool:
    """Constant-time password comparison."""
    if candidate is None:
        return False
    return hmac.compare_digest(candidate, settings.APP_PASSWORD)


def token_from_request(headers, cookies, query_params, allow_query: bool = True) -> Optional[str]:
    """Extracts a session token from a request.

    Order: ``Authorization: Bearer`` (mobile) -> query string (EventSource) ->
    cookie (browser).
    """
    authorization = headers.get("authorization") if headers else None
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    # Session tokens are never accepted from the query string: only the
    # short-lived stream ticket is, and callers must opt in explicitly.
    if allow_query and query_params is not None:
        query_token = query_params.get("token")
        if query_token:
            return query_token

    if cookies is not None:
        return cookies.get(settings.AUTH_COOKIE_NAME)

    return None


def is_public_path(path: str) -> bool:
    """True when the path needs no session (health, docs, login)."""
    normalized = path.rstrip("/") or "/"
    for public in PUBLIC_PATHS:
        candidate = public.rstrip("/") or "/"
        if normalized == candidate:
            return True
    return False
