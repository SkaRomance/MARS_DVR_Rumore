import uuid

import pytest
from httpx import AsyncClient

AUTH_PREFIX = "/api/v1/noise/auth"


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient, test_admin_user):
    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": test_admin_user.email, "password": "testpassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_admin_user):
    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": test_admin_user.email, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient, test_tenant):
    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": "nobody@test.com", "password": "somepassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, test_inactive_user):
    response = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": test_inactive_user.email, "password": "testpassword123"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_me_with_valid_token(client: AsyncClient, auth_headers, test_admin_user):
    response = await client.get(f"{AUTH_PREFIX}/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_admin_user.email
    assert data["role"] == "admin"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    response = await client.get(f"{AUTH_PREFIX}/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client: AsyncClient):
    response = await client.get(
        f"{AUTH_PREFIX}/me",
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_valid(client: AsyncClient, test_admin_user):
    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": test_admin_user.email, "password": "testpassword123"},
    )
    tokens = login_resp.json()
    response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_token_expired_or_invalid(client: AsyncClient):
    response = await client.post(
        f"{AUTH_PREFIX}/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_as_admin_same_tenant(client: AsyncClient, auth_headers, test_tenant):
    new_email = f"newuser-{uuid.uuid4().hex[:8]}@test.com"
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": new_email,
            "password": "NewUser1password",
            "full_name": "New User",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == new_email
    assert data["role"] == "consultant"
    assert data["full_name"] == "New User"


@pytest.mark.asyncio
async def test_register_as_admin_different_tenant(client: AsyncClient, auth_headers):
    other_tenant_id = str(uuid.uuid4())
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": "cross-tenant@test.com",
            "password": "Some1password",
            "role": "consultant",
            "tenant_id": other_tenant_id,
        },
    )
    assert response.status_code == 403
    assert "other tenants" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, auth_headers, test_tenant, test_admin_user):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": test_admin_user.email,
            "password": "Another1password",
            "full_name": "Duplicate",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_without_auth(client: AsyncClient, test_tenant):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        json={
            "email": "noauth@test.com",
            "password": "somepassword",
            "full_name": "No Auth",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient, auth_headers, test_tenant):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": f"short-{uuid.uuid4().hex[:6]}@test.com",
            "password": "Ab1",
            "full_name": "Short Pass",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 422
    assert "8" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient, auth_headers, test_tenant):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": f"noupper-{uuid.uuid4().hex[:6]}@test.com",
            "password": "lowercase1",
            "full_name": "No Upper",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 422
    assert "uppercase" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient, auth_headers, test_tenant):
    response = await client.post(
        f"{AUTH_PREFIX}/register",
        headers=auth_headers,
        json={
            "email": f"nodigit-{uuid.uuid4().hex[:6]}@test.com",
            "password": "NoDigitsHere",
            "full_name": "No Digit",
            "role": "consultant",
            "tenant_id": str(test_tenant.id),
        },
    )
    assert response.status_code == 422
    assert "digit" in response.json()["detail"].lower()
