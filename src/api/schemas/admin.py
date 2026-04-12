from uuid import UUID
from pydantic import BaseModel


class LogoUploadResponse(BaseModel):
    tenant_id: UUID
    logo_mime_type: str
    message: str


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    license_status: str
    max_assessments: int
    logo_mime_type: str | None = None