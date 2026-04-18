"""SuggestionServiceV2 — context-scoped CRUD for AISuggestion.

The Wave 29 frontend expects context-id-keyed endpoints with a
specific JSON shape:
  { id, suggestion_type, payload_json, confidence, status, ... }

The underlying AISuggestion model (Wave 16-23) uses `content` and
`confidence_score`. This service adapts between the two without
renaming DB columns (which would break existing routes).

Supported operations:
- list_by_context(context_id, status?)       → list[dict]
- create(context_id, suggestion_type, payload, confidence, ...) → dict
- approve(suggestion_id, edited_payload?)    → dict
- reject(suggestion_id, reason?)             → dict
- bulk_action(ids, action, **options)        → {processed, total, failed[]}

All operations are tenant-scoped: cross-tenant access raises
SuggestionNotFoundError (caller maps to 404 — don't leak existence).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.ai_suggestion import (
    AISuggestion,
    AISuggestionStatus,
)

logger = logging.getLogger(__name__)


class SuggestionNotFoundError(Exception):
    """Suggestion missing or not in caller's tenant."""


class InvalidStatusTransitionError(Exception):
    """Attempted to approve/reject an already-resolved suggestion."""


BulkAction = Literal["approve", "reject"]


class SuggestionServiceV2:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── reads ──────────────────────────────────────────────────────

    async def list_by_context(
        self,
        *,
        context_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(AISuggestion)
            .where(AISuggestion.tenant_id == tenant_id)
            .where(AISuggestion.context_id == context_id)
            .order_by(desc(AISuggestion.priority), desc(AISuggestion.created_at))
        )
        if status and status != "all":
            stmt = stmt.where(AISuggestion.status == status)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def get(
        self, *, suggestion_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> AISuggestion:
        stmt = select(AISuggestion).where(
            AISuggestion.id == suggestion_id,
            AISuggestion.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise SuggestionNotFoundError(
                f"Suggestion {suggestion_id} not found in tenant {tenant_id}"
            )
        return row

    # ── writes ─────────────────────────────────────────────────────

    async def create(
        self,
        *,
        context_id: uuid.UUID,
        tenant_id: uuid.UUID,
        suggestion_type: str,
        title: str,
        payload_json: dict[str, Any],
        confidence: float | None = None,
        risk_band: str | None = None,
        priority: int | None = None,
    ) -> dict[str, Any]:
        row = AISuggestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            context_id=context_id,
            suggestion_type=suggestion_type,
            title=title[:255],
            content=payload_json,
            confidence_score=confidence,
            risk_band=risk_band,
            priority=priority,
            status=AISuggestionStatus.PENDING,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dict(row)

    async def approve(
        self,
        *,
        suggestion_id: uuid.UUID,
        tenant_id: uuid.UUID,
        approved_by: str | None = None,
        edited_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = await self.get(suggestion_id=suggestion_id, tenant_id=tenant_id)
        if row.status not in (AISuggestionStatus.PENDING, AISuggestionStatus.MODIFIED):
            raise InvalidStatusTransitionError(
                f"Cannot approve suggestion in status '{row.status}'"
            )

        if edited_payload is not None:
            row.content = edited_payload
            row.status = AISuggestionStatus.MODIFIED
            # Preserve approval metadata separately — MODIFIED means
            # the consultant edited-and-approved, not just approved as-is.
        row.status = AISuggestionStatus.APPROVED
        row.approved_by = approved_by
        from datetime import datetime, timezone
        row.approved_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dict(row)

    async def reject(
        self,
        *,
        suggestion_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self.get(suggestion_id=suggestion_id, tenant_id=tenant_id)
        if row.status not in (AISuggestionStatus.PENDING, AISuggestionStatus.MODIFIED):
            raise InvalidStatusTransitionError(
                f"Cannot reject suggestion in status '{row.status}'"
            )
        row.status = AISuggestionStatus.REJECTED
        row.rejection_reason = reason
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dict(row)

    async def bulk_action(
        self,
        *,
        suggestion_ids: list[uuid.UUID],
        tenant_id: uuid.UUID,
        action: BulkAction,
        min_confidence: float | None = None,
        approved_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Apply an action to many suggestions in one transaction.

        If min_confidence is given, only suggestions meeting the threshold
        are processed (filter applied per-row during iteration).
        Returns {processed, total_requested, failed[{id, reason}]}.
        """
        processed = 0
        failed: list[dict[str, Any]] = []

        for sid in suggestion_ids:
            try:
                row = await self.get(suggestion_id=sid, tenant_id=tenant_id)
            except SuggestionNotFoundError:
                failed.append({"id": str(sid), "reason": "not_found"})
                continue

            if min_confidence is not None and (
                row.confidence_score is None
                or row.confidence_score < min_confidence
            ):
                failed.append({"id": str(sid), "reason": "below_confidence_threshold"})
                continue

            try:
                if action == "approve":
                    await self.approve(
                        suggestion_id=sid,
                        tenant_id=tenant_id,
                        approved_by=approved_by,
                    )
                elif action == "reject":
                    await self.reject(
                        suggestion_id=sid,
                        tenant_id=tenant_id,
                        reason=reason,
                    )
                else:
                    failed.append({"id": str(sid), "reason": f"unknown_action:{action}"})
                    continue
                processed += 1
            except InvalidStatusTransitionError as exc:
                failed.append({"id": str(sid), "reason": str(exc)})

        return {
            "processed": processed,
            "total_requested": len(suggestion_ids),
            "failed": failed,
        }

    # ── serialization ──────────────────────────────────────────────

    @staticmethod
    def _to_dict(row: AISuggestion) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "context_id": str(row.context_id) if row.context_id else None,
            "suggestion_type": row.suggestion_type,
            "title": row.title,
            "payload_json": row.content,
            "confidence": row.confidence_score,
            "risk_band": row.risk_band,
            "priority": row.priority,
            "status": row.status,
            "approved_by": row.approved_by,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "rejection_reason": row.rejection_reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
