"""Correlation-ID middleware: read/generate X-Request-ID per request.

The middleware:

* Reads the ``X-Request-ID`` header on the incoming request when present.
* Generates a fresh UUID4 id when the header is missing.
* Binds the id to the structlog contextvars so any log line emitted during
  the request includes ``request_id=<uuid>``.
* Sets the same header on the outgoing response, making the id visible to
  clients and reverse-proxies for end-to-end tracing.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to every request and response.

    The incoming header name defaults to ``X-Request-ID`` and may be
    overridden when constructing the middleware. The bound structlog
    context is cleared again at the end of the request to avoid
    leaking state between requests served by the same worker.
    """

    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        finally:
            # Always clear contextvars so we don't leak state between requests.
            structlog.contextvars.clear_contextvars()

        response.headers[self.header_name] = request_id
        return response
