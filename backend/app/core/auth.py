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


def issue_token(
    ttl_seconds: Optional[int] = None, token_version: int = 0
) -> Tuple[str, int]:
    """Creates a signed session token.

    ``token_version`` is compared against the value stored server-side on every
    request, so incrementing it revokes every existing session immediately
    (logout-everywhere, password rotation) without keeping a token table.

    Returns the token and its expiry as a unix timestamp.
    """
    ttl = settings.AUTH_TOKEN_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now = int(time.time())
    expires_at = now + ttl
    payload = {
        "iat": now,
        "exp": expires_at,
        "scope": "session",
        "ver": int(token_version),
        "nonce": secrets.token_hex(8),
    }
    return _sign_payload(payload)


def token_version_of(token: Optional[str]) -> Optional[int]:
    """Returns the version claim of a signature-valid token, else None."""
    if not token or "." not in token:
        return None
    encoded, _, signature = token.partition(".")
    expected = _b64encode(
        hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload: Dict[str, Any] = json.loads(_b64decode(encoded))
        return int(payload.get("ver", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def issue_stream_ticket(
    ttl_seconds: int = 120, token_version: int = 0
) -> Tuple[str, int]:
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
    payload = {
        "iat": now,
        "exp": expires_at,
        "scope": "stream",
        "ver": int(token_version),
        "nonce": secrets.token_hex(8),
    }
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


PBKDF2_ITERATIONS = 260_000


def hash_password(plain: str) -> str:
    """PBKDF2-HMAC-SHA256 hash with a per-password random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password_hash(plain: str, stored: str) -> bool:
    """Checks a password against a stored PBKDF2 hash."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt.encode("ascii"), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def password_matches(candidate: Optional[str], stored_hash: Optional[str] = None) -> bool:
    """Constant-time password comparison.

    When a stored hash exists (the operator changed the password from the UI)
    it takes precedence over the environment default.
    """
    if candidate is None:
        return False
    # An empty hash means "no rotation yet" (the row may exist only to hold a
    # token version), so the environment value stays authoritative.
    if stored_hash:
        return verify_password_hash(candidate, stored_hash)
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
