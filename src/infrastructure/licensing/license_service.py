from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.licensing.keygen_client import KeygenClient


class LicenseService:
    def __init__(self, db_session: AsyncSession, keygen_client: KeygenClient, grace_period_hours: int = 24):
        self.db = db_session
        self.keygen = keygen_client
        self.grace_period_hours = grace_period_hours

    async def activate_license(self, tenant_id: UUID, license_key: str, fingerprint: str) -> dict:
        from src.infrastructure.database.models.tenant import Tenant

        validation = await self.keygen.validate_license(license_key)
        if validation is None:
            return {"status": "error", "detail": "License validation failed or Keygen API unavailable"}

        license_data = validation.get("data", validation)
        attrs = license_data.get("attributes", license_data)
        status = attrs.get("status", "unknown")
        plan = attrs.get("name", "unknown")
        expires = attrs.get("expiry")

        if status not in ("ACTIVE", "active"):
            return {"status": "error", "detail": f"License status is {status}"}

        activation = await self.keygen.activate_license(license_key, fingerprint)
        if activation is None:
            return {"status": "error", "detail": "License activation failed"}

        machine_data = activation.get("data", activation)
        machine_attrs = machine_data.get("attributes", machine_data)
        machine_id = machine_data.get("id", machine_attrs.get("id"))

        entitlements = await self.keygen.check_entitlements(license_key)
        features = []
        if entitlements:
            for ent in entitlements:
                ent_attrs = ent.get("attributes", {})
                code = ent_attrs.get("code", ent.get("id", ""))
                if code:
                    features.append(code)

        max_assessments = 10
        for f in features:
            if f.startswith("max_assessments_"):
                try:
                    max_assessments = int(f.split("_")[-1])
                except ValueError:
                    pass

        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "detail": "Tenant not found"}

        tenant.license_status = "active"
        tenant.keygen_license_id = license_key
        tenant.plan = plan
        tenant.max_assessments = max_assessments
        tenant.license_activated_at = datetime.now(timezone.utc)
        tenant.license_expires_at = expires
        tenant.machine_id = machine_id

        await self.db.commit()

        return {
            "status": "active",
            "plan": plan,
            "features": features,
            "expires_at": expires,
        }

    async def deactivate_license(self, tenant_id: UUID) -> dict:
        from src.infrastructure.database.models.tenant import Tenant

        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "detail": "Tenant not found"}

        machine_id = getattr(tenant, "machine_id", None)
        if machine_id:
            await self.keygen.deactivate_license(machine_id)

        tenant.license_status = "inactive"
        tenant.keygen_license_id = None
        tenant.machine_id = None
        tenant.license_activated_at = None
        tenant.license_expires_at = None

        await self.db.commit()

        return {"status": "inactive"}

    async def get_license_status(self, tenant_id: UUID) -> dict:
        from src.infrastructure.database.models.tenant import Tenant

        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "detail": "Tenant not found"}

        current_status = tenant.license_status

        license_id = tenant.keygen_license_id
        if license_id and current_status == "active":
            validation = await self.keygen.validate_license(license_id)
            if validation is None:
                activated_at = getattr(tenant, "license_activated_at", None)
                if activated_at:
                    now = datetime.now(timezone.utc)
                    if activated_at.tzinfo is None:
                        activated_at = activated_at.replace(tzinfo=timezone.utc)
                    if now - activated_at < timedelta(hours=self.grace_period_hours):
                        return {
                            "status": "active",
                            "plan": tenant.plan or "unknown",
                            "license_key_masked": self._mask_key(license_id),
                            "activated_at": activated_at.isoformat() if activated_at else None,
                            "expires_at": getattr(tenant, "license_expires_at", None),
                            "features": [],
                            "grace_period": True,
                        }
                return {
                    "status": "unknown",
                    "plan": tenant.plan or "unknown",
                    "license_key_masked": self._mask_key(license_id),
                    "activated_at": None,
                    "expires_at": None,
                    "features": [],
                }

            license_data = validation.get("data", validation)
            attrs = license_data.get("attributes", license_data)
            remote_status = attrs.get("status", "unknown")

            if remote_status not in ("ACTIVE", "active"):
                tenant.license_status = "inactive"
                await self.db.commit()
                return {
                    "status": "inactive",
                    "plan": tenant.plan or "unknown",
                    "license_key_masked": self._mask_key(license_id),
                    "activated_at": None,
                    "expires_at": None,
                    "features": [],
                }

            entitlements = await self.keygen.check_entitlements(license_id)
            features = []
            if entitlements:
                for ent in entitlements:
                    ent_attrs = ent.get("attributes", {})
                    code = ent_attrs.get("code", ent.get("id", ""))
                    if code:
                        features.append(code)

            return {
                "status": "active",
                "plan": tenant.plan or attrs.get("name", "unknown"),
                "license_key_masked": self._mask_key(license_id),
                "activated_at": getattr(tenant, "license_activated_at", None),
                "expires_at": getattr(tenant, "license_expires_at", None) or attrs.get("expiry"),
                "features": features,
            }

        return {
            "status": current_status or "inactive",
            "plan": tenant.plan or "unknown",
            "license_key_masked": self._mask_key(license_id) if license_id else None,
            "activated_at": getattr(tenant, "license_activated_at", None),
            "expires_at": getattr(tenant, "license_expires_at", None),
            "features": [],
        }

    async def get_usage(self, tenant_id: UUID) -> dict:
        from src.infrastructure.database.models.tenant import Tenant
        from src.infrastructure.database.models.noise_assessment import NoiseAssessment

        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return {"status": "error", "detail": "Tenant not found"}

        count_result = await self.db.execute(
            select(sa_func.count()).select_from(NoiseAssessment).where(
                NoiseAssessment._is_deleted == False
            )
        )
        assessments_used = count_result.scalar() or 0
        max_assessments = tenant.max_assessments or 0

        license_status = await self.get_license_status(tenant_id)
        features = license_status.get("features", [])

        return {
            "tenant_id": str(tenant_id),
            "plan": tenant.plan or "unknown",
            "assessments_used": assessments_used,
            "assessments_limit": max_assessments,
            "features": features,
        }

    async def check_feature(self, tenant_id: UUID, feature: str) -> bool:
        license_status = await self.get_license_status(tenant_id)
        if license_status.get("status") != "active":
            return False
        features = license_status.get("features", [])
        return feature in features

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key or len(key) <= 8:
            return "****"
        return key[:4] + "*" * (len(key) - 8) + key[-4:]