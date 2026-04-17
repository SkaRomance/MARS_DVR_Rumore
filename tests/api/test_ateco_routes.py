import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

ATECO_PREFIX = "/api/v1/noise/ateco"


@pytest.fixture
async def ateco_tenant(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="ATECO Test Tenant",
        slug=f"ateco-test-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def ateco_user(db_session: AsyncSession, ateco_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=ateco_tenant.id,
        email="ateco@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="ATECO Tester",
        role="consultant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def ateco_auth_headers(ateco_user):
    token = create_access_token(
        {
            "sub": str(ateco_user.id),
            "tenant_id": str(ateco_user.tenant_id),
            "role": ateco_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_macro_categories_requires_auth(client: AsyncClient):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_macro_categories_returns_all(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories", headers=ateco_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 21


@pytest.mark.asyncio
async def test_list_macro_categories_structure(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories", headers=ateco_auth_headers)
    assert response.status_code == 200
    data = response.json()
    first = data[0]
    assert "code" in first
    assert "name_it" in first
    assert "name_en" in first
    assert "description_it" in first
    assert "description_en" in first
    assert "typical_sources" in first
    assert "typical_lex_range" in first
    assert isinstance(first["typical_sources"], list)
    assert isinstance(first["typical_lex_range"], list)
    assert len(first["typical_lex_range"]) == 2


@pytest.mark.asyncio
async def test_get_single_macro_category_valid(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories/C", headers=ateco_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "C"
    assert "manifattur" in data["name_it"].lower()


@pytest.mark.asyncio
async def test_get_single_macro_category_not_found(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories/Z", headers=ateco_auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_single_macro_category_requires_auth(client: AsyncClient):
    response = await client.get(f"{ATECO_PREFIX}/macro-categories/C")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_ateco_code_info_valid(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/code/25.11.00", headers=ateco_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ateco_code"] == "25.11.00"
    assert data["macro_category"] is not None
    assert data["macro_category"]["code"] == "C"


@pytest.mark.asyncio
async def test_get_ateco_code_info_unknown_division(client: AsyncClient, ateco_auth_headers):
    response = await client.get(f"{ATECO_PREFIX}/code/04.99.99", headers=ateco_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ateco_code"] == "04.99.99"
    assert data["macro_category"] is None


@pytest.mark.asyncio
async def test_get_ateco_code_info_requires_auth(client: AsyncClient):
    response = await client.get(f"{ATECO_PREFIX}/code/25.11.00")
    assert response.status_code == 401
