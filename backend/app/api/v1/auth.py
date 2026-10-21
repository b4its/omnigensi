"""Password login for the single-operator deployment."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.auth import (
    issue_token,
    password_matches,
    token_from_request,
    verify_token,
)
from app.core.config import settings
from app.schemas.system import LoginRequest, LoginResponse, SessionInfo

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
async def login(payload: LoginRequest, response: Response) -> Any:
    """Exchanges the operator password for a session.

    Sets an httpOnly cookie for browsers and returns the token in the body so
    a native mobile client can send it as a bearer token.
    """
    if not settings.AUTH_ENABLED:
        return LoginResponse(
            authenticated=True,
            auth_enabled=False,
            token=None,
            expires_at=None,
        )

    if not password_matches(payload.password):
        logger.warning("Failed login attempt from %s", getattr(response, "client", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

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
