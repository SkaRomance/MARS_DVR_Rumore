from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.admin import LogoUploadResponse, TenantResponse
from src.bootstrap.database import get_db
from src.domain.services.logo_service import validate_logo
from src.infrastructure.auth.dependencies import (
    get_current_tenant,
    get_current_user,
    require_role,
)
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User, UserRole
from src.infrastructure.middleware.rate_limiter import default_limiter

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/tenant/logo", response_model=LogoUploadResponse, status_code=status.HTTP_200_OK)
async def upload_logo(
    upload: UploadFile = File(...),
    content_type: str = Form(...),
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate=Depends(default_limiter),
):
    content = await upload.read()
    mime_type = upload.content_type or content_type
    try:
        validated_data, validated_mime = validate_logo(content, mime_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    tenant.logo_data = validated_data
    tenant.logo_mime_type = validated_mime
    await db.commit()

    return LogoUploadResponse(
        tenant_id=tenant.id,
        logo_mime_type=validated_mime,
        message="Logo uploaded successfully",
    )


@router.get("/tenant/logo")
async def get_logo(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    _rate=Depends(default_limiter),
):
    if not tenant.logo_data or not tenant.logo_mime_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo found")

    return Response(content=tenant.logo_data, media_type=tenant.logo_mime_type)


@router.delete("/tenant/logo", status_code=status.HTTP_200_OK)
async def delete_logo(
    current_user: User = Depends(require_role(UserRole.admin)),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate=Depends(default_limiter),
):
    tenant.logo_data = None
    tenant.logo_mime_type = None
    await db.commit()

    return {"message": "Logo deleted successfully"}


@router.get("/tenant", response_model=TenantResponse)
async def get_tenant(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    _rate=Depends(default_limiter),
):
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        license_status=tenant.license_status,
        max_assessments=tenant.max_assessments,
        logo_mime_type=tenant.logo_mime_type,
    )
