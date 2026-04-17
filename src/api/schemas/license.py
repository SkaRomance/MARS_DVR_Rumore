from uuid import UUID

from pydantic import BaseModel


class LicenseActivateRequest(BaseModel):
    license_key: str
    machine_fingerprint: str


class LicenseDeactivateRequest(BaseModel):
    pass


class LicenseStatusResponse(BaseModel):
    tenant_id: UUID
    license_status: str
    plan: str
    license_key_masked: str | None = None
    activated_at: str | None = None
    expires_at: str | None = None
    features: list[str] = []


class LicenseUsageResponse(BaseModel):
    tenant_id: UUID
    plan: str
    assessments_used: int
    assessments_limit: int
    features: list[str] = []
