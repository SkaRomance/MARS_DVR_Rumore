import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from src.infrastructure.auth.dependencies import require_license, require_role
from src.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from src.infrastructure.auth.password import (
    PasswordPolicyError,
    get_password_hash,
    validate_password_policy,
    verify_password,
)
from src.infrastructure.database.models.user import UserRole


class TestCreateAccessToken:
    def test_create_access_token_valid(self):
        token = create_access_token({"sub": "123", "tenant_id": "456"})
        payload = verify_token(token)
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self):
        delta = timedelta(minutes=5)
        before = datetime.now(UTC).replace(microsecond=0)
        token = create_access_token({"sub": "123"}, expires_delta=delta)
        payload = verify_token(token)
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=UTC)
        after = datetime.now(UTC)
        assert before + delta <= exp_dt <= after + delta + timedelta(seconds=5)


class TestCreateRefreshToken:
    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "123"})
        payload = verify_token(token)
        assert payload["sub"] == "123"
        assert payload["type"] == "refresh"


class TestVerifyToken:
    def test_verify_token_valid(self):
        token = create_access_token({"sub": "123"})
        payload = verify_token(token)
        assert payload["sub"] == "123"

    def test_verify_token_expired(self):
        token = create_access_token({"sub": "123"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_token(token)

    def test_verify_token_wrong_secret(self):
        token = create_access_token({"sub": "123"})
        fake_settings = MagicMock()
        fake_settings.jwt_secret_key = "completely-different-secret-key"
        fake_settings.jwt_algorithm = "HS256"
        with patch(
            "src.infrastructure.auth.jwt_handler.get_settings",
            return_value=fake_settings,
        ):
            with pytest.raises((jwt.InvalidSignatureError, jwt.DecodeError)):
                verify_token(token)


class TestValidatePasswordPolicy:
    def test_validate_password_policy_valid(self):
        validate_password_policy("TestPass1")

    def test_validate_password_policy_too_short(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("Ab1")

    def test_validate_password_policy_no_uppercase(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("testpass1")

    def test_validate_password_policy_no_lowercase(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("TESTPASS1")

    def test_validate_password_policy_no_digit(self):
        with pytest.raises(PasswordPolicyError):
            validate_password_policy("TestPassword")


class TestPasswordHashing:
    def test_get_password_hash(self):
        hashed = get_password_hash("TestPass1")
        assert isinstance(hashed, str)
        assert hashed != "TestPass1"
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = get_password_hash("TestPass1")
        assert verify_password("TestPass1", hashed) is True

    def test_verify_password_wrong(self):
        hashed = get_password_hash("TestPass1")
        assert verify_password("WrongPass1", hashed) is False


class TestDependenciesIntegration:
    @pytest.mark.asyncio
    async def test_get_current_user_valid(self, client, auth_headers):
        response = await client.get("/api/v1/noise/companies/", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client):
        response = await client.get(
            "/api/v1/noise/companies/",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, client, test_admin_user):
        from src.infrastructure.auth.jwt_handler import create_access_token

        token = create_access_token(
            {
                "sub": str(test_admin_user.id),
                "tenant_id": str(test_admin_user.tenant_id),
            },
            expires_delta=timedelta(seconds=-1),
        )
        response = await client.get(
            "/api/v1/noise/companies/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_require_role_insufficient(self, client, db_session, test_tenant):
        from src.infrastructure.database.models.user import User

        viewer_user = User(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            email="viewer-roletest@test.com",
            hashed_password=get_password_hash("TestPass1xyz"),
            full_name="Viewer User",
            role="viewer",
            is_active=True,
        )
        db_session.add(viewer_user)
        await db_session.commit()
        await db_session.refresh(viewer_user)

        checker = require_role(UserRole.admin)
        with pytest.raises(Exception) as exc_info:
            await checker(viewer_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_license_no_license(self, test_tenant):
        from fastapi import HTTPException

        test_tenant.license_status = "inactive"
        test_tenant.license_activated_at = None
        db_mock = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await require_license(current_user=MagicMock(), tenant=test_tenant, db=db_mock)
        assert exc_info.value.status_code == 403
