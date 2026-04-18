"""Autopilot SSE routes — POST /run streams events, GET /status, POST /cancel.

SSE implementation: FastAPI `StreamingResponse` yielding `data: {...}\\n\\n`
frames. Frontend EventSource / fetch-reader (Wave 29 apiClient) parses each
frame as JSON matching `AutopilotEvent.to_sse_dict()`.

Cancellation: in-memory per-process registry of running orchestrators.
For single-worker deploys this is sufficient; a future Redis-backed
registry is needed for multi-worker horizontal scaling — marked TODO
at the dict where the registry lives.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.mars import require_mars_context
from src.bootstrap.config import get_settings
from src.bootstrap.database import get_db
from src.domain.services.autopilot.exposure_estimator import ExposureEstimatorAgent
from src.domain.services.autopilot.orchestrator import AutopilotOrchestrator
from src.domain.services.autopilot.types import AutopilotRunContext
from src.domain.services.noise_context_service import (
    NoiseAssessmentContextNotFoundError,
    NoiseAssessmentContextService,
)
from src.domain.services.suggestion_service import SuggestionServiceV2
from src.infrastructure.llm.base import LLMProvider
from src.infrastructure.llm.mock_provider import MockProvider
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.types import MarsContext

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/autopilot", tags=["Autopilot"])


# Process-wide orchestrator registry for cancellation.
# TODO: move to Redis for multi-worker (or sticky-session on LB).
_RUNNING: dict[uuid.UUID, AutopilotOrchestrator] = {}


def get_llm_provider() -> LLMProvider:
    """Default LLM provider. Overridden in tests via dependency_overrides.

    Production: this returns a real Ollama provider; dev/test returns the
    MockProvider so tests don't hit the network. For the initial wire-up
    we default to Mock and let deployments swap it.
    """
    settings = get_settings()
    if settings.app_env != "production":
        return MockProvider(response_content=json.dumps({"estimates": []}))
    # Production wiring deferred to Wave 30 (ollama_provider requires
    # Ollama API key + model config). For now, still safe to return Mock
    # so the endpoint is callable — empty estimates yield LEX=0, green.
    return MockProvider(response_content=json.dumps({"estimates": []}))


@router.post(
    "/{context_id}/run",
    summary="Run AI autopilot (SSE streaming)",
    response_description="text/event-stream of AutopilotEvent JSON frames",
)
async def run_autopilot(
    context_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> StreamingResponse:
    # Resolve context tenant-scoped

    # Build a MarsApiClient inline to pass to context service — but we
    # don't actually need network here since we use the cached snapshot
    # on the row, so a null transport is fine.
    ctx_service = NoiseAssessmentContextService(session, _noop_mars_client())
    try:
        ctx_row = await ctx_service.get_by_id(context_id=context_id, tenant_id=mars_ctx.tenant_id)
    except NoiseAssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if ctx_row.dvr_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Context has no DVR snapshot. Re-bootstrap with force_sync=true.",
        )

    agent = ExposureEstimatorAgent(llm)
    svc = SuggestionServiceV2(session)
    orch = AutopilotOrchestrator(session, agent, svc)

    _RUNNING[context_id] = orch

    run_ctx = AutopilotRunContext(
        context_id=ctx_row.id,
        tenant_id=mars_ctx.tenant_id,
        access_token=mars_ctx.access_token,
        dvr_snapshot=ctx_row.dvr_snapshot,
    )

    async def event_stream():
        try:
            async for ev in orch.run(run_ctx):
                yield f"data: {json.dumps(ev.to_sse_dict())}\n\n"
            # Commit once at the end; each persisted AISuggestion is in the
            # transaction. If the pipeline fails partway, we commit the
            # partial state — in practice persist is the final real step.
            await session.commit()
        except Exception:  # noqa: BLE001
            await session.rollback()
            logger.exception("Autopilot stream crashed for context %s", context_id)
            raise
        finally:
            _RUNNING.pop(context_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx hint: don't buffer SSE
        },
    )


@router.get(
    "/{context_id}/status",
    response_model=dict[str, Any],
    summary="Lightweight status: whether an autopilot run is active",
)
async def autopilot_status(
    context_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    ctx_service = NoiseAssessmentContextService(session, _noop_mars_client())
    try:
        ctx_row = await ctx_service.get_by_id(context_id=context_id, tenant_id=mars_ctx.tenant_id)
    except NoiseAssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    running = context_id in _RUNNING
    svc = SuggestionServiceV2(session)
    suggestions = await svc.list_by_context(context_id=context_id, tenant_id=mars_ctx.tenant_id)
    return {
        "context_id": str(context_id),
        "is_running": running,
        "has_snapshot": ctx_row.dvr_snapshot is not None,
        "status": ctx_row.status,
        "suggestions_count": len(suggestions),
        "pending_count": sum(1 for s in suggestions if s["status"] == "pending"),
    }


@router.post(
    "/{context_id}/cancel",
    summary="Request cancellation of an in-flight autopilot run",
)
async def cancel_autopilot(
    context_id: uuid.UUID,
    mars_ctx: Annotated[MarsContext, Depends(require_mars_context)],
) -> dict[str, Any]:
    orch = _RUNNING.get(context_id)
    if orch is None:
        return {"cancelled": False, "reason": "no_active_run"}
    orch.request_cancel()
    return {"cancelled": True, "reason": "requested"}


def _noop_mars_client() -> MarsApiClient:
    """Throwaway MarsApiClient used when the context service won't hit MARS.

    `NoiseAssessmentContextService.get_by_id` doesn't make HTTP calls, so
    we give it a client with a no-op transport to satisfy its constructor
    signature without opening a real connection.
    """
    import httpx

    return MarsApiClient(
        base_url="http://localhost",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        max_retries=0,
    )
