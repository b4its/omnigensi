"""Uniform error handling shared by web and mobile clients.

FastAPI's default error body is ``{"detail": "..."}`` for business errors but
``{"detail": [{...}]}`` for validation errors. Mobile clients cannot branch on
that reliably, so every failure is normalised to a single envelope::

    {"success": false, "detail": "<string>", "code": "<code>",
     "errors": [...], "request_id": "<id>"}
"""

import logging
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("omnigensi.errors")

REQUEST_ID_HEADER = "X-Request-ID"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _frame(
    detail: str,
    code: str,
    status_code: int,
    request: Request,
    errors: Any = None,
) -> JSONResponse:
    request_id = _request_id(request)
    payload: Dict[str, Any] = {
        "success": False,
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def install_error_handlers(app: FastAPI) -> None:
    """Register exception handlers that emit the uniform error envelope."""

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        errors = None
        if isinstance(detail, list):
            # Some FastAPI internals raise HTTPException with a list detail.
            errors = detail
            detail = "Request failed validation"
        code = _STATUS_CODES.get(exc.status_code, "error")
        return _frame(str(detail), code, exc.status_code, request, errors)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        first = errors[0]["msg"] if errors else "Request failed validation"
        return _frame(
            first,
            "validation_error",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            request,
            errors,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return _frame(
            "An unexpected server error occurred",
            "internal_error",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            request,
        )
