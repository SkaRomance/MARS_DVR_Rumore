import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

audit_logger = structlog.get_logger("audit_middleware")

MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method in MUTATING_METHODS:
            audit_logger.info(
                "http_request",
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                client_ip=request.client.host if request.client else None,
            )

        return response