import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import (
    event,
    String as SAString,
    LargeBinary as SALargeBinary,
    Text as SAText,
    JSON,
    TypeDecorator,
    types as satypes,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB

_mock_limiter = MagicMock()
_mock_limiter.init = AsyncMock()
_mock_limiter.close = AsyncMock()

import sys

sys.modules.setdefault(
    "fastapi_limiter",
    MagicMock(FastAPILimiter=_mock_limiter),
)
sys.modules.setdefault("fastapi_limiter.depends", MagicMock())

from src.bootstrap.main import app
from src.bootstrap.database import get_db
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.base import Base
from src.infrastructure.middleware.rate_limiter import (
    auth_limiter,
    ai_limiter,
    export_limiter,
    default_limiter,
    license_limiter,
)

NOOP_LIMITERS = {
    auth_limiter: lambda: True,
    ai_limiter: lambda: True,
    export_limiter: lambda: True,
    default_limiter: lambda: True,
    license_limiter: lambda: True,
}

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_db.sqlite3"


class SQLiteUUID(TypeDecorator):
    impl = SAString(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


def _replace_pg_types_with_sqlite():
    type_map = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            original_type = column.type
            if isinstance(original_type, PG_UUID):
                type_map[column] = original_type
                column.type = SQLiteUUID()
            elif isinstance(original_type, PG_JSONB):
                type_map[column] = original_type
                column.type = JSON()
            elif isinstance(original_type, SALargeBinary):
                type_map[column] = original_type
                column.type = SAText()
            elif (
                hasattr(original_type, "__class__")
                and original_type.__class__.__name__ == "LargeBinary"
            ):
                type_map[column] = original_type
                column.type = SAText()
    return type_map


def _restore_pg_types(type_map):
    for column, original_type in type_map.items():
        column.type = original_type


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    type_map = _replace_pg_types_with_sqlite()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import sqlite3

    sqlite3.register_adapter(uuid.UUID, lambda val: str(val))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
    _restore_pg_types(type_map)


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        trans = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            yield session
        await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    for limiter_dep, noop in NOOP_LIMITERS.items():
        app.dependency_overrides[limiter_dep] = noop

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession):
    from src.infrastructure.database.models.tenant import Tenant

    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
        slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession, test_tenant):
    from src.infrastructure.database.models.user import User

    user = User(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="admin@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_inactive_user(db_session: AsyncSession, test_tenant):
    from src.infrastructure.database.models.user import User

    user = User(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="inactive@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Inactive User",
        role="consultant",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_admin_user):
    from src.infrastructure.auth.jwt_handler import create_access_token

    token = create_access_token(
        {
            "sub": str(test_admin_user.id),
            "tenant_id": str(test_admin_user.tenant_id),
            "role": test_admin_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}
