"""Password login for the single-operator deployment."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.auth import (
    issue_stream_ticket,
    issue_token,
    password_matches,
    token_from_request,
    verify_token,
)
from app.core.config import settings
from app.core.rate_limit import client_key, login_throttle
from app.schemas.system import (
    LoginRequest,
    LoginResponse,
    SessionInfo,
    StreamTicketResponse,
)

logger = logging.getLogger("omnigensi.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.AUTH_TOKEN_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> Any:
    """Exchanges the operator password for a session.

    Sets an httpOnly cookie for browsers and returns the token in the body so
    a native mobile client can send it as a bearer token.

    Failed attempts are throttled per client address: a short default password
    must not be brute-forceable.
    """
    if not settings.AUTH_ENABLED:
        return LoginResponse(
            authenticated=True,
            auth_enabled=False,
            token=None,
            expires_at=None,
        )

    key = client_key(request)

    wait = login_throttle.retry_after(key)
    if wait:
        logger.warning(
            "Login attempt from %s rejected: locked out for %ss more", key, wait
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )

    if not password_matches(payload.password):
        lockout = login_throttle.record_failure(key)
        logger.warning(
            "Failed login attempt from %s%s",
            key,
            f" (locked out for {lockout}s)" if lockout else "",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

    login_throttle.record_success(key)

    token, expires_at = issue_token()
    _set_session_cookie(response, token)
    logger.info("Operator signed in")
    return LoginResponse(
        authenticated=True,
        auth_enabled=True,
        token=token,
        expires_at=expires_at,
    )


@router.post("/logout", response_model=SessionInfo)
async def logout(response: Response) -> Any:
    """Clears the session cookie.

    Tokens are stateless, so a bearer token the client already holds stays
    valid until it expires; clients should discard it locally.
    """
    _clear_session_cookie(response)
    return SessionInfo(
        authenticated=False,
        auth_enabled=settings.AUTH_ENABLED,
    )


@router.get("/session", response_model=SessionInfo)
async def session(request: Request) -> Any:
    """Reports whether the caller is signed in.

    Public on purpose: the login screen calls it to decide whether to show
    the password prompt.
    """
    token: Optional[str] = token_from_request(
        request.headers, request.cookies, request.query_params
    )
    authenticated = not settings.AUTH_ENABLED or verify_token(token)
    return SessionInfo(
        authenticated=authenticated,
        auth_enabled=settings.AUTH_ENABLED,
    )


@router.post("/stream-ticket", response_model=StreamTicketResponse)
async def create_stream_ticket(request: Request) -> Any:
    """Exchanges a valid session for a short-lived, stream-scoped ticket.

    The ticket is the only credential accepted in a URL, so the long-lived
    session token never appears in access logs or Referer headers.
    """
    if not settings.AUTH_ENABLED:
        # Nothing to exchange; the caller needs no credential at all.
        ticket, expires_at = issue_stream_ticket()
        return StreamTicketResponse(ticket=ticket, expires_at=expires_at)

    token = token_from_request(
        request.headers, request.cookies, request.query_params, allow_query=False
    )
    if not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid session is required to obtain a stream ticket",
        )

    ticket, expires_at = issue_stream_ticket()
    return StreamTicketResponse(ticket=ticket, expires_at=expires_at)
