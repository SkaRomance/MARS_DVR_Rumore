import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

RAG_PREFIX = "/api/v1/noise/rag"


@pytest.fixture
async def rag_tenant(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="RAG Test Tenant",
        slug=f"rag-test-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def rag_admin_user(db_session: AsyncSession, rag_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=rag_tenant.id,
        email="rag_admin@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="RAG Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def rag_consultant_user(db_session: AsyncSession, rag_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=rag_tenant.id,
        email="rag_consultant@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="RAG Consultant",
        role="consultant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def rag_admin_headers(rag_admin_user):
    token = create_access_token(
        {
            "sub": str(rag_admin_user.id),
            "tenant_id": str(rag_admin_user.tenant_id),
            "role": rag_admin_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def rag_consultant_headers(rag_consultant_user):
    token = create_access_token(
        {
            "sub": str(rag_consultant_user.id),
            "tenant_id": str(rag_consultant_user.tenant_id),
            "role": rag_consultant_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_rag_query_requires_auth(client: AsyncClient):
    response = await client.post(
        f"{RAG_PREFIX}/query",
        json={"query": "test query here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rag_query_success(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(
        return_value=[
            {
                "text": " chunk about noise exposure",
                "metadata": {
                    "source_file": "test.pdf",
                    "category": "Rumore",
                    "subcategory": "generale",
                    "page_number": 1,
                },
                "relevance_score": 0.95,
            }
        ]
    )
    mock_rag.build_context = MagicMock(return_value="Contesto rumore industriale")

    with patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag):
        response = await client.post(
            f"{RAG_PREFIX}/query",
            json={"query": "esposizione rumore industriale", "n_results": 5},
            headers=rag_admin_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "esposizione rumore industriale"
    assert data["total_found"] == 1
    assert data["context"] is not None
    assert len(data["results"]) == 1
    assert data["results"][0]["source_file"] == "test.pdf"


@pytest.mark.asyncio
async def test_rag_query_validation_too_short(client: AsyncClient, rag_admin_headers):
    response = await client.post(
        f"{RAG_PREFIX}/query",
        json={"query": "ab"},
        headers=rag_admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rag_query_failure(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(side_effect=Exception("ChromaDB error"))

    with patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag):
        response = await client.post(
            f"{RAG_PREFIX}/query",
            json={"query": "test query here"},
            headers=rag_admin_headers,
        )

    assert response.status_code == 500
    assert "RAG query failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rag_index_requires_admin(client: AsyncClient, rag_consultant_headers):
    response = await client.post(
        f"{RAG_PREFIX}/index",
        headers=rag_consultant_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rag_index_success(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.index_documents = AsyncMock(return_value=42)
    mock_rag.get_stats = MagicMock(
        return_value={
            "collection_name": "test_collection",
            "total_chunks": 42,
            "chroma_dir": "data/chroma_db",
        }
    )

    mock_extractor = MagicMock()
    mock_extractor.extract_to_dicts = MagicMock(return_value=[{"text": "page1", "metadata": {}}])

    with (
        patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag),
        patch("src.api.routes.rag_routes.PDFExtractor", return_value=mock_extractor),
    ):
        response = await client.post(
            f"{RAG_PREFIX}/index",
            headers=rag_admin_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["pages_extracted"] == 1
    assert data["chunks_indexed"] == 42


@pytest.mark.asyncio
async def test_rag_index_with_reset(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.reset_collection = MagicMock()
    mock_rag.index_documents = AsyncMock(return_value=42)
    mock_rag.get_stats = MagicMock(
        return_value={
            "collection_name": "test_collection",
            "total_chunks": 42,
            "chroma_dir": "data/chroma_db",
        }
    )

    mock_extractor = MagicMock()
    mock_extractor.extract_to_dicts = MagicMock(return_value=[{"text": "page1", "metadata": {}}])

    with (
        patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag),
        patch("src.api.routes.rag_routes.PDFExtractor", return_value=mock_extractor),
    ):
        response = await client.post(
            f"{RAG_PREFIX}/index?reset=true",
            headers=rag_admin_headers,
        )

    assert response.status_code == 200
    mock_rag.reset_collection.assert_called_once()


@pytest.mark.asyncio
async def test_rag_stats_success(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.get_stats = MagicMock(
        return_value={
            "collection_name": "mars_noise_rag",
            "total_chunks": 19915,
            "chroma_dir": "data/chroma_db",
        }
    )

    with patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag):
        response = await client.get(
            f"{RAG_PREFIX}/stats",
            headers=rag_admin_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["collection_name"] == "mars_noise_rag"
    assert data["total_chunks"] == 19915
    assert data["chroma_dir"] == "data/chroma_db"


@pytest.mark.asyncio
async def test_rag_stats_error(client: AsyncClient, rag_admin_headers):
    mock_rag = MagicMock()
    mock_rag.get_stats = MagicMock(return_value={"error": "ChromaDB not initialized"})

    with patch("src.api.routes.rag_routes.RAGService", return_value=mock_rag):
        response = await client.get(
            f"{RAG_PREFIX}/stats",
            headers=rag_admin_headers,
        )

    assert response.status_code == 503
