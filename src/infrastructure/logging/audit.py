import structlog
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.database import get_db
from src.infrastructure.database.models.audit_log import AuditLog

logger = structlog.get_logger("audit")


async def log_audit(
    action: str,
    resource_type: str,
    resource_id: str | UUID | None = None,
    tenant_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
):
    logger.info(
        "audit_event",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        tenant_id=str(tenant_id) if tenant_id else None,
        user_id=str(user_id) if user_id else None,
        details=details,
        ip_address=ip_address,
    )

    try:
        async with get_db() as session:
            entry = AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
                details=details,
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.error("audit_log_write_failed", action=action, resource_type=resource_type)