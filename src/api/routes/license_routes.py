from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas.license import (
    LicenseActivateRequest,
    LicenseDeactivateRequest,
    LicenseStatusResponse,
    LicenseUsageResponse,
)
from src.bootstrap.config import get_settings
from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import (
    get_current_user,
    get_current_tenant,
    require_role,
)
from src.infrastructure.database.models.user import UserRole
from src.infrastructure.licensing.keygen_client import KeygenClient
from src.infrastructure.licensing.license_service import LicenseService
from src.infrastructure.middleware.rate_limiter import license_limiter

router = APIRouter(prefix="/license", tags=["License"])

_admin_only = require_role(UserRole.admin)


async def _get_license_service(db=Depends(get_db)) -> LicenseService:
    settings = get_settings()
    client = KeygenClient(
        api_url=settings.keygen_api_url,
        account_id=settings.keygen_account_id,
        admin_token=settings.keygen_admin_token,
    )
    return LicenseService(
        db_session=db,
        keygen_client=client,
        grace_period_hours=settings.license_grace_period_hours,
    )


@router.post("/activate", response_model=LicenseStatusResponse)
async def activate_license(
    body: LicenseActivateRequest,
    _admin=Depends(_admin_only),
    tenant=Depends(get_current_tenant),
    service: LicenseService = Depends(_get_license_service),
    _rate=Depends(license_limiter),
):
    result = await service.activate_license(
        tenant_id=tenant.id,
        license_key=body.license_key,
        fingerprint=body.machine_fingerprint,
    )
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("detail", "Activation failed"),
        )

    license_status = await service.get_license_status(tenant.id)
    return LicenseStatusResponse(
        tenant_id=tenant.id,
        license_status=license_status.get("status", "active"),
        plan=license_status.get("plan", "unknown"),
        license_key_masked=license_status.get("license_key_masked"),
        activated_at=license_status.get("activated_at"),
        expires_at=license_status.get("expires_at"),
        features=license_status.get("features", []),
    )


@router.post("/deactivate")
async def deactivate_license(
    body: LicenseDeactivateRequest,
    _admin=Depends(_admin_only),
    tenant=Depends(get_current_tenant),
    service: LicenseService = Depends(_get_license_service),
    _rate=Depends(license_limiter),
):
    result = await service.deactivate_license(tenant_id=tenant.id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("detail", "Deactivation failed"),
        )
    return {"status": "deactivated"}


@router.get("/status", response_model=LicenseStatusResponse)
async def get_license_status(
    _user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    service: LicenseService = Depends(_get_license_service),
    _rate=Depends(license_limiter),
):
    license_status = await service.get_license_status(tenant.id)
    if license_status.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=license_status.get("detail", "Tenant not found"),
        )
    return LicenseStatusResponse(
        tenant_id=tenant.id,
        license_status=license_status.get("status", "inactive"),
        plan=license_status.get("plan", "unknown"),
        license_key_masked=license_status.get("license_key_masked"),
        activated_at=license_status.get("activated_at"),
        expires_at=license_status.get("expires_at"),
        features=license_status.get("features", []),
    )


@router.get("/usage", response_model=LicenseUsageResponse)
async def get_usage(
    _user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    service: LicenseService = Depends(_get_license_service),
    _rate=Depends(license_limiter),
):
    usage = await service.get_usage(tenant.id)
    if usage.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=usage.get("detail", "Tenant not found"),
        )
    return LicenseUsageResponse(
        tenant_id=tenant.id,
        plan=usage.get("plan", "unknown"),
        assessments_used=usage.get("assessments_used", 0),
        assessments_limit=usage.get("assessments_limit", 0),
        features=usage.get("features", []),
    )
