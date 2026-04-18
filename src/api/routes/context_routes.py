"""Routes for NoiseAssessmentContext — the bridge between MARS and Rumore.

All endpoints require a valid MARS bearer token (require_mars_context
handles 401/402/503 mapping). The resulting context is scoped to the
caller's tenant: cross-tenant access is 404, not 403, so existence
is not leaked.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.mars import get_mars_client, require_mars_context
from src.api.schemas.context import (
    ContextBootstrapRequest,
    ContextListResponse,
    ContextResponse,
    ContextStatusUpdateRequest,
)
from src.bootstrap.database import get_db
from src.domain.services.noise_context_service import (
    NoiseAssessmentContextNotFoundError,
    NoiseAssessmentContextService,
)
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContextStatus,
)
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsApiError, MarsAuthError, MarsNotFoundError
from src.infrastructure.mars.types import MarsContext

router = APIRouter(prefix="/contexts", tags=["Noise Contexts"])


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[MarsApiClient, Depends(get_mars_client)],
) -> NoiseAssessmentContextService:
    return NoiseAssessmentContextService(session, client)


@router.post(
    "/bootstrap",
    response_model=ContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Bootstrap or resume a Rumore session for a MARS DVR",
)
async def bootstrap_context(
    body: ContextBootstrapRequest,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    svc: Annotated[NoiseAssessmentContextService, Depends(_service)],
) -> ContextResponse:
    try:
        ctx = await svc.bootstrap(
            tenant_id=mars_ctx.tenant_id,
            user_id=mars_ctx.user_id,
            mars_dvr_document_id=body.mars_dvr_document_id,
            mars_revision_id=body.mars_revision_id,
            access_token=mars_ctx.access_token,
            force_sync=body.force_sync,
        )
        await session.commit()
    except MarsNotFoundError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DVR {body.mars_dvr_document_id} not found in MARS",
        ) from exc
    except MarsAuthError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    except MarsApiError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MARS upstream unavailable",
        ) from exc

    return ContextResponse.model_validate(ctx)


@router.get(
    "/{context_id}",
    response_model=ContextResponse,
    summary="Get a context by id (tenant-scoped)",
)
async def get_context(
    context_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    svc: Annotated[NoiseAssessmentContextService, Depends(_service)],
) -> ContextResponse:
    try:
        ctx = await svc.get_by_id(context_id=context_id, tenant_id=mars_ctx.tenant_id)
    except NoiseAssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ContextResponse.model_validate(ctx)


@router.get(
    "/by-dvr/{mars_dvr_document_id}",
    response_model=ContextResponse,
    summary="Lookup the most recent context for a MARS DVR document",
)
async def get_context_by_dvr(
    mars_dvr_document_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    svc: Annotated[NoiseAssessmentContextService, Depends(_service)],
) -> ContextResponse:
    try:
        ctx = await svc.get_by_dvr(
            tenant_id=mars_ctx.tenant_id,
            mars_dvr_document_id=mars_dvr_document_id,
        )
    except NoiseAssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ContextResponse.model_validate(ctx)


@router.get(
    "/",
    response_model=ContextListResponse,
    summary="List contexts for the caller's tenant",
)
async def list_contexts(
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    svc: Annotated[NoiseAssessmentContextService, Depends(_service)],
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ContextListResponse:
    items = await svc.list_by_tenant(
        tenant_id=mars_ctx.tenant_id,
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    return ContextListResponse(
        items=[ContextResponse.model_validate(c) for c in items],
        total=len(items),
    )


@router.patch(
    "/{context_id}/status",
    response_model=ContextResponse,
    summary="Update context lifecycle status",
)
async def update_context_status(
    context_id: uuid.UUID,
    body: ContextStatusUpdateRequest,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    svc: Annotated[NoiseAssessmentContextService, Depends(_service)],
) -> ContextResponse:
    try:
        status_enum = NoiseAssessmentContextStatus(body.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{body.status}'. "
                   f"Valid: {[s.value for s in NoiseAssessmentContextStatus]}",
        ) from exc

    try:
        ctx = await svc.update_status(
            context_id=context_id,
            tenant_id=mars_ctx.tenant_id,
            status=status_enum,
        )
        await session.commit()
    except NoiseAssessmentContextNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ContextResponse.model_validate(ctx)
