"""NoiseAssessmentContextService — orchestration for MARS-bound assessment sessions.

Responsibilities:
- Bootstrap a context from MARS identifiers (get-or-create semantics)
- Fetch and cache the MARS DVR snapshot
- Refresh stale snapshots on bootstrap (default threshold 7 days)
- Look up contexts by DVR document or context id, scoped to tenant

Boundaries:
- Wraps a SQLAlchemy AsyncSession (injected, not owned — the caller
  decides transaction scope).
- Wraps a MarsApiClient for snapshot retrieval.
- Does NOT commit by itself; the route handler / use-case commits so
  transaction boundaries align with HTTP request scope.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
    NoiseAssessmentContextStatus,
)
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsApiError, MarsNotFoundError
from src.infrastructure.mars.types import MarsDvrRevisionResponse

logger = logging.getLogger(__name__)


DEFAULT_SNAPSHOT_STALE_AFTER = timedelta(days=7)


class NoiseAssessmentContextNotFoundError(Exception):
    """Raised when a context lookup fails within the caller's tenant."""


class NoiseAssessmentContextService:
    def __init__(
        self,
        session: AsyncSession,
        mars_client: MarsApiClient,
        snapshot_stale_after: timedelta = DEFAULT_SNAPSHOT_STALE_AFTER,
    ):
        self.session = session
        self.client = mars_client
        self._stale_after = snapshot_stale_after

    async def bootstrap(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        mars_dvr_document_id: uuid.UUID,
        mars_revision_id: uuid.UUID | None,
        access_token: str,
        force_sync: bool = False,
    ) -> NoiseAssessmentContext:
        """Get or create a context for this (tenant, doc, revision).

        If mars_revision_id is None, we first ask MARS for the latest
        revision and use that id. This lets the frontend call bootstrap
        with just a doc id when the user doesn't know the revision.
        """
        # Resolve revision id if not given (one MARS call either way)
        snapshot: MarsDvrRevisionResponse | None = None
        if mars_revision_id is None or force_sync:
            try:
                snapshot = await self.client.get_dvr_revision(access_token, mars_dvr_document_id, mars_revision_id)
                mars_revision_id = snapshot.id
            except MarsNotFoundError:
                raise
            except MarsApiError as exc:
                logger.warning("MARS snapshot fetch failed during bootstrap: %s", exc)
                if mars_revision_id is None:
                    raise  # Cannot proceed without revision id
                # else keep going — maybe we have a cached context already

        # Look up existing
        existing = await self._find(
            tenant_id=tenant_id,
            mars_dvr_document_id=mars_dvr_document_id,
            mars_revision_id=mars_revision_id,
        )

        if existing is not None and not force_sync and not self._is_stale(existing):
            return existing

        if snapshot is None:
            # Need to fetch snapshot before we can create/refresh
            snapshot = await self.client.get_dvr_revision(access_token, mars_dvr_document_id, mars_revision_id)

        if existing is not None:
            self._apply_snapshot(existing, snapshot, user_id=user_id)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        ctx = NoiseAssessmentContext(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            mars_dvr_document_id=mars_dvr_document_id,
            mars_revision_id=mars_revision_id,
            mars_document_version=snapshot.version,
            dvr_snapshot=snapshot.snapshot.model_dump(mode="json", by_alias=True),
            dvr_schema_version=snapshot.snapshot.schema_version,
            status=NoiseAssessmentContextStatus.bootstrapped.value,
            last_synced_at=datetime.now(UTC),
        )
        self.session.add(ctx)
        await self.session.flush()
        await self.session.refresh(ctx)
        return ctx

    async def get_by_dvr(
        self,
        *,
        tenant_id: uuid.UUID,
        mars_dvr_document_id: uuid.UUID,
    ) -> NoiseAssessmentContext:
        """Return the most recent context for a DVR doc within tenant."""
        stmt = (
            select(NoiseAssessmentContext)
            .where(NoiseAssessmentContext.tenant_id == tenant_id)
            .where(NoiseAssessmentContext.mars_dvr_document_id == mars_dvr_document_id)
            .order_by(desc(NoiseAssessmentContext.updated_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        ctx = result.scalar_one_or_none()
        if ctx is None:
            raise NoiseAssessmentContextNotFoundError(
                f"No context for DVR {mars_dvr_document_id} in tenant {tenant_id}"
            )
        return ctx

    async def get_by_id(self, *, context_id: uuid.UUID, tenant_id: uuid.UUID) -> NoiseAssessmentContext:
        """Fetch by id, scoped to tenant (404 for cross-tenant access)."""
        stmt = (
            select(NoiseAssessmentContext)
            .where(NoiseAssessmentContext.id == context_id)
            .where(NoiseAssessmentContext.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        ctx = result.scalar_one_or_none()
        if ctx is None:
            raise NoiseAssessmentContextNotFoundError(f"Context {context_id} not found in tenant {tenant_id}")
        return ctx

    async def list_by_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[NoiseAssessmentContext]:
        stmt = (
            select(NoiseAssessmentContext)
            .where(NoiseAssessmentContext.tenant_id == tenant_id)
            .order_by(desc(NoiseAssessmentContext.updated_at))
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(NoiseAssessmentContext.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        *,
        context_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status: NoiseAssessmentContextStatus,
    ) -> NoiseAssessmentContext:
        ctx = await self.get_by_id(context_id=context_id, tenant_id=tenant_id)
        ctx.status = status.value
        await self.session.flush()
        # Refresh to pick up server-updated updated_at, else accessing it
        # after route's commit triggers async I/O in sync pydantic context
        await self.session.refresh(ctx)
        return ctx

    # ── internal ───────────────────────────────────────────────────

    async def _find(
        self,
        *,
        tenant_id: uuid.UUID,
        mars_dvr_document_id: uuid.UUID,
        mars_revision_id: uuid.UUID,
    ) -> NoiseAssessmentContext | None:
        stmt = (
            select(NoiseAssessmentContext)
            .where(NoiseAssessmentContext.tenant_id == tenant_id)
            .where(NoiseAssessmentContext.mars_dvr_document_id == mars_dvr_document_id)
            .where(NoiseAssessmentContext.mars_revision_id == mars_revision_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _is_stale(self, ctx: NoiseAssessmentContext) -> bool:
        if ctx.last_synced_at is None:
            return True
        synced = ctx.last_synced_at
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        return datetime.now(UTC) - synced > self._stale_after

    @staticmethod
    def _apply_snapshot(
        ctx: NoiseAssessmentContext,
        snapshot: MarsDvrRevisionResponse,
        *,
        user_id: uuid.UUID | None,
    ) -> None:
        ctx.mars_document_version = snapshot.version
        ctx.dvr_snapshot = snapshot.snapshot.model_dump(mode="json", by_alias=True)
        ctx.dvr_schema_version = snapshot.snapshot.schema_version
        ctx.last_synced_at = datetime.now(UTC)
        if user_id is not None:
            ctx.user_id = user_id
