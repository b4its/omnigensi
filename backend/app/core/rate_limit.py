"""In-process brute-force protection for the login endpoint.

The instance is guarded by a single short default password, so an
unthrottled login endpoint is the weakest link in the whole deployment.

Design:
* Sliding window per client key (IP by default): N failed attempts within the
  window trigger a temporary lockout with exponential backoff.
* A successful login clears the counter for that key.
* Everything is in-process, which is sufficient for the single-container
  deployment this project ships. A multi-worker deployment would need a
  shared store (Redis) - documented rather than pretended.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("omnigensi.auth")


@dataclass
class _AttemptRecord:
    failures: List[float] = field(default_factory=list)
    locked_until: float = 0.0


class LoginThrottle:
    """Tracks failed logins per client key and enforces lockouts."""

    def __init__(
        self,
        max_attempts: Optional[int] = None,
        window_seconds: Optional[int] = None,
        base_lockout_seconds: Optional[int] = None,
    ) -> None:
        self._records: Dict[str, _AttemptRecord] = {}
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._base_lockout = base_lockout_seconds

    # Settings are read lazily so tests can monkeypatch them.
    @property
    def max_attempts(self) -> int:
        return self._max_attempts or settings.AUTH_MAX_LOGIN_ATTEMPTS

    @property
    def window_seconds(self) -> int:
        return self._window_seconds or settings.AUTH_LOGIN_WINDOW_SECONDS

    @property
    def base_lockout(self) -> int:
        return self._base_lockout or settings.AUTH_LOCKOUT_SECONDS

    def _prune(self, record: _AttemptRecord, now: float) -> None:
        cutoff = now - self.window_seconds
        record.failures = [ts for ts in record.failures if ts > cutoff]

    def retry_after(self, key: str) -> int:
        """Seconds the caller must wait, or 0 when not locked out."""
        record = self._records.get(key)
        if not record:
            return 0
        now = time.time()
        if record.locked_until > now:
            return max(1, int(record.locked_until - now))
        return 0

    def record_failure(self, key: str) -> int:
        """Registers a failed attempt. Returns the lockout seconds applied."""
        now = time.time()
        record = self._records.setdefault(key, _AttemptRecord())
        self._prune(record, now)
        record.failures.append(now)

        if len(record.failures) < self.max_attempts:
            return 0

        # Exponential backoff per consecutive lockout cycle.
        over = len(record.failures) - self.max_attempts
        lockout = min(self.base_lockout * (2**over), 3600)
        record.locked_until = now + lockout
        logger.warning(
            "Login lockout for %s: %ss after %s failures in %ss",
            key,
            lockout,
            len(record.failures),
            self.window_seconds,
        )
        return lockout

    def record_success(self, key: str) -> None:
        self._records.pop(key, None)

    def reset(self) -> None:
        """Test helper: clears all state."""
        self._records.clear()


login_throttle = LoginThrottle()


def client_key(request) -> str:
    """Identifies a caller for throttling purposes.

    Uses the socket peer address. ``X-Forwarded-For`` is deliberately ignored
    because any client can forge it; a reverse proxy deployment should be
    configured to rewrite ``request.client`` instead.
    """
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host or "unknown"
