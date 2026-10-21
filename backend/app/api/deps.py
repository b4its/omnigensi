"""Shared query-parameter dependencies."""

from fastapi import Query

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Pagination:
    """Standard ``limit``/``offset`` pagination for list endpoints.

    Collection endpoints keep returning a bare JSON array (so the existing web
    UI and mobile clients stay backwards compatible) and expose the window via
    the ``X-Total-Count`` / ``X-Limit`` / ``X-Offset`` response headers.
    """

    def __init__(
        self,
        limit: int = Query(
            DEFAULT_LIMIT,
            ge=1,
            le=MAX_LIMIT,
            description="Maximum number of items to return",
        ),
        offset: int = Query(
            0,
            ge=0,
            description="Number of items to skip before collecting the page",
        ),
    ) -> None:
        self.limit = limit
        self.offset = offset
