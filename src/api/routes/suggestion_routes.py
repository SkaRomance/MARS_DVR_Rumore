"""V2 suggestion routes — context-scoped, matching Wave 29 frontend contract."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.mars import require_mars_context
from src.api.schemas.suggestion import (
    SuggestionApproveRequest,
    SuggestionBulkRequest,
    SuggestionBulkResponse,
    SuggestionRejectRequest,
)
from src.bootstrap.database import get_db
from src.domain.services.suggestion_service import (
    InvalidStatusTransitionError,
    SuggestionNotFoundError,
    SuggestionServiceV2,
)
from src.infrastructure.mars.types import MarsContext

router = APIRouter(prefix="/suggestions", tags=["Suggestions V2"])


def _service(session: Annotated[AsyncSession, Depends(get_db)]) -> SuggestionServiceV2:
    return SuggestionServiceV2(session)


@router.get(
    "/by-context/{context_id}",
    response_model=list[dict[str, Any]],
    summary="List suggestions for a context",
)
async def list_by_context(
    context_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    svc: Annotated[SuggestionServiceV2, Depends(_service)],
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return await svc.list_by_context(
        context_id=context_id,
        tenant_id=mars_ctx.tenant_id,
        status=status_filter,
    )


@router.post(
    "/{suggestion_id}/approve",
    response_model=dict[str, Any],
    summary="Approve a suggestion (optionally with edits)",
)
async def approve_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionApproveRequest,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    svc: Annotated[SuggestionServiceV2, Depends(_service)],
) -> dict[str, Any]:
    try:
        result = await svc.approve(
            suggestion_id=suggestion_id,
            tenant_id=mars_ctx.tenant_id,
            approved_by=mars_ctx.email,
            edited_payload=body.edited_payload,
        )
        await session.commit()
    except SuggestionNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return result


@router.post(
    "/{suggestion_id}/reject",
    response_model=dict[str, Any],
    summary="Reject a suggestion",
)
async def reject_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionRejectRequest,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    svc: Annotated[SuggestionServiceV2, Depends(_service)],
) -> dict[str, Any]:
    try:
        result = await svc.reject(
            suggestion_id=suggestion_id,
            tenant_id=mars_ctx.tenant_id,
            reason=body.reason,
        )
        await session.commit()
    except SuggestionNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return result


@router.post(
    "/bulk",
    response_model=SuggestionBulkResponse,
    summary="Approve/reject many suggestions at once",
)
async def bulk_action(
    body: SuggestionBulkRequest,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    svc: Annotated[SuggestionServiceV2, Depends(_service)],
) -> SuggestionBulkResponse:
    result = await svc.bulk_action(
        suggestion_ids=body.suggestion_ids,
        tenant_id=mars_ctx.tenant_id,
        action=body.action,
        min_confidence=body.min_confidence,
        approved_by=mars_ctx.email,
        reason=body.reason,
    )
    await session.commit()
    return SuggestionBulkResponse(**result)
