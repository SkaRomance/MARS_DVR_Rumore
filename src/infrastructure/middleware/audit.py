import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

audit_logger = structlog.get_logger("audit_middleware")

MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method in MUTATING_METHODS:
            user_id = None
            tenant_id = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from src.infrastructure.auth.jwt_handler import verify_token

                    payload = verify_token(auth_header[7:])
                    user_id = payload.get("sub")
                    tenant_id = payload.get("tenant_id")
                except Exception:
                    pass

            audit_logger.info(
                "http_request",
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                client_ip=request.client.host if request.client else None,
                user_id=user_id,
                tenant_id=tenant_id,
            )

            session = None
            try:
                from src.bootstrap.database import get_session_factory
                from src.infrastructure.database.models.audit_log import AuditLog

                session = get_session_factory()()
                async with session:
                    entry = AuditLog(
                        action=f"{request.method} {request.url.path}",
                        resource_type="api_request",
                        resource_id=str(tenant_id) if tenant_id else None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        details={"status_code": response.status_code},
                        ip_address=request.client.host if request.client else None,
                    )
                    session.add(entry)
                    await session.commit()
            except Exception:
                audit_logger.warning("audit_db_write_failed")
            finally:
                if session:
                    await session.close()

        return response
