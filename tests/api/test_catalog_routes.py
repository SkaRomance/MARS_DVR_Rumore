import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.noise_source import NoiseSourceCatalog

CATALOG_PREFIX = "/api/v1/noise/catalog"


def _make_source(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        marca="TestBrand",
        modello="TestModel",
        tipologia="compressore",
        alimentazione="elettrico",
        laeq_min_db_a=70.0,
        laeq_max_db_a=90.0,
        laeq_typical_db_a=80.0,
        lcpeak_db_c=100.0,
        fonte="PAF - Portale Agenti Fisici",
        url_fonte=None,
        data_aggiornamento=date(2025, 1, 1),
        disclaimer="Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici",
        version=1,
        _is_deleted=False,
    )
    defaults.update(overrides)
    return NoiseSourceCatalog(**defaults)


@pytest.mark.asyncio
async def test_list_catalog_empty(client: AsyncClient, auth_headers):
    response = await client.get(f"{CATALOG_PREFIX}/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_catalog_with_data(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    source = _make_source(tenant_id=test_tenant.id)
    db_session.add(source)
    await db_session.commit()

    response = await client.get(f"{CATALOG_PREFIX}/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["marca"] == "TestBrand"
    assert data[0]["modello"] == "TestModel"
    assert data[0]["tipologia"] == "compressore"


@pytest.mark.asyncio
async def test_list_catalog_filter_tipologia(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    s1 = _make_source(tenant_id=test_tenant.id, tipologia="compressore", marca="A")
    s2 = _make_source(tenant_id=test_tenant.id, tipologia="martello", marca="B")
    db_session.add_all([s1, s2])
    await db_session.commit()

    response = await client.get(
        f"{CATALOG_PREFIX}/",
        params={"tipologia": "compressore"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tipologia"] == "compressore"


@pytest.mark.asyncio
async def test_list_catalog_filter_marca(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    s1 = _make_source(tenant_id=test_tenant.id, marca="DeWalt", modello="X1")
    s2 = _make_source(tenant_id=test_tenant.id, marca="Bosch", modello="Y2")
    db_session.add_all([s1, s2])
    await db_session.commit()

    response = await client.get(
        f"{CATALOG_PREFIX}/",
        params={"marca": "dew"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["marca"] == "DeWalt"


@pytest.mark.asyncio
async def test_list_catalog_filter_laeq_range(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    s1 = _make_source(tenant_id=test_tenant.id, laeq_typical_db_a=75.0, marca="Quiet")
    s2 = _make_source(tenant_id=test_tenant.id, laeq_typical_db_a=95.0, marca="Loud")
    db_session.add_all([s1, s2])
    await db_session.commit()

    response = await client.get(
        f"{CATALOG_PREFIX}/",
        params={"min_laeq": 70.0, "max_laeq": 80.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["marca"] == "Quiet"


@pytest.mark.asyncio
async def test_catalog_stats(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    s1 = _make_source(tenant_id=test_tenant.id, tipologia="compressore")
    s2 = _make_source(tenant_id=test_tenant.id, tipologia="compressore")
    s3 = _make_source(tenant_id=test_tenant.id, tipologia="martello")
    db_session.add_all([s1, s2, s3])
    await db_session.commit()

    response = await client.get(f"{CATALOG_PREFIX}/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_sources"] == 3
    assert data["by_tipologia"]["compressore"] == 2
    assert data["by_tipologia"]["martello"] == 1


@pytest.mark.asyncio
async def test_get_catalog_source(client: AsyncClient, auth_headers, db_session: AsyncSession, test_tenant):
    source = _make_source(tenant_id=test_tenant.id)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    response = await client.get(
        f"{CATALOG_PREFIX}/{source.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(source.id)
    assert data["marca"] == "TestBrand"
    assert data["disclaimer"] is not None


@pytest.mark.asyncio
async def test_get_catalog_source_not_found(client: AsyncClient, auth_headers):
    random_id = str(uuid.uuid4())
    response = await client.get(
        f"{CATALOG_PREFIX}/{random_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_catalog_source_invalid_id(client: AsyncClient, auth_headers):
    response = await client.get(
        f"{CATALOG_PREFIX}/not-a-uuid",
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_catalog_unauthenticated(client: AsyncClient):
    response = await client.get(f"{CATALOG_PREFIX}/")
    assert response.status_code == 401
