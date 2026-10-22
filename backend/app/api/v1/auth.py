"""Password login for the single-operator deployment."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.auth import (
    hash_password,
    issue_stream_ticket,
    issue_token,
    password_matches,
    token_from_request,
    verify_token,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.auth_credential import AuthCredential
from app.core.rate_limit import client_key, login_throttle
from app.schemas.system import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    SessionInfo,
    StreamTicketResponse,
)

logger = logging.getLogger("omnigensi.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _stored_password_hash(db: AsyncSession) -> Optional[str]:
    """Returns the rotated password hash, or None to fall back to the env."""
    row = (
        await db.execute(select(AuthCredential).order_by(AuthCredential.updated_at.desc()).limit(1))
    ).scalar_one_or_none()
    return row.password_hash if row else None


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
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Any:
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

    stored_hash = await _stored_password_hash(db)
    if not password_matches(payload.password, stored_hash):
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


@router.post("/change-password", response_model=SessionInfo)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Rotates the shared operator password.

    The new password is stored as a PBKDF2 hash and takes precedence over the
    APP_PASSWORD default. Existing session tokens stay valid until they expire,
    so the caller is signed out and must log in again with the new password.
    """
    if not settings.AUTH_ENABLED:
        raise HTTPException(
            status_code=400, detail="Authentication is disabled on this instance"
        )

    token = token_from_request(
        request.headers, request.cookies, request.query_params, allow_query=False
    )
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="A valid session is required")

    stored_hash = await _stored_password_hash(db)
    if not password_matches(payload.current_password, stored_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=400, detail="The new password must differ from the current one"
        )
    if payload.new_password == "123":
        raise HTTPException(
            status_code=400,
            detail="The default password cannot be used; choose a stronger one",
        )

    new_hash = hash_password(payload.new_password)
    existing = (
        await db.execute(select(AuthCredential).limit(1))
    ).scalar_one_or_none()
    if existing:
        existing.password_hash = new_hash
    else:
        db.add(AuthCredential(password_hash=new_hash))
    await db.commit()

    # Force a fresh login with the new password.
    _clear_session_cookie(response)
    logger.info("Operator password rotated")

    return SessionInfo(authenticated=False, auth_enabled=settings.AUTH_ENABLED)
