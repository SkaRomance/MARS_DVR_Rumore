"""Integration tests for SuggestionServiceV2 (SQLite via conftest)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.suggestion_service import (
    InvalidStatusTransitionError,
    SuggestionNotFoundError,
    SuggestionServiceV2,
)
from src.infrastructure.database.models.ai_suggestion import (
    AISuggestion,
    AISuggestionStatus,
)
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
)
from src.infrastructure.database.models.tenant import Tenant


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def context(db_session: AsyncSession, tenant: Tenant) -> NoiseAssessmentContext:
    ctx = NoiseAssessmentContext(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        mars_dvr_document_id=uuid.uuid4(),
        mars_revision_id=uuid.uuid4(),
        mars_document_version=1,
        status="bootstrapped",
    )
    db_session.add(ctx)
    await db_session.flush()
    return ctx


async def _seed(session, *, context, tenant, **over) -> AISuggestion:
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        context_id=context.id,
        suggestion_type="phase_laeq",
        title="Test suggestion",
        content={"laeq_db": 85.0, "duration_hours": 2.5},
        confidence_score=0.72,
        status=AISuggestionStatus.PENDING,
    )
    defaults.update(over)
    row = AISuggestion(**defaults)
    session.add(row)
    await session.flush()
    return row


# ── create ─────────────────────────────────────────────────────────


async def test_create_suggestion(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    result = await svc.create(
        context_id=context.id,
        tenant_id=tenant.id,
        suggestion_type="phase_laeq",
        title="Stima fase 1",
        payload_json={"phase_name": "Taglio", "laeq_db": 92.0, "duration_hours": 2.0},
        confidence=0.85,
        risk_band="red",
        priority=1,
    )
    assert uuid.UUID(result["id"])
    assert result["suggestion_type"] == "phase_laeq"
    assert result["payload_json"]["laeq_db"] == 92.0
    assert result["confidence"] == pytest.approx(0.85)
    assert result["status"] == AISuggestionStatus.PENDING


# ── list_by_context ───────────────────────────────────────────────


async def test_list_by_context_filters_by_status(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.PENDING)
    await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.APPROVED)
    await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.REJECTED)

    all_items = await svc.list_by_context(context_id=context.id, tenant_id=tenant.id)
    pending_only = await svc.list_by_context(context_id=context.id, tenant_id=tenant.id, status="pending")
    approved_only = await svc.list_by_context(context_id=context.id, tenant_id=tenant.id, status="approved")

    assert len(all_items) == 3
    assert len(pending_only) == 1
    assert len(approved_only) == 1
    assert pending_only[0]["status"] == "pending"


async def test_list_by_context_tenant_isolation(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    # Seed in our tenant
    await _seed(db_session, context=context, tenant=tenant)

    # Seed under another tenant but same context_id (edge case)
    other_tenant = Tenant(id=uuid.uuid4(), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(other_tenant)
    await db_session.flush()
    await _seed(db_session, context=context, tenant=other_tenant)

    # List scoped to our tenant returns only ours
    rows = await svc.list_by_context(context_id=context.id, tenant_id=tenant.id)
    assert len(rows) == 1


# ── approve ────────────────────────────────────────────────────────


async def test_approve_pending(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await _seed(db_session, context=context, tenant=tenant)

    result = await svc.approve(suggestion_id=row.id, tenant_id=tenant.id, approved_by="consultant@example.com")
    assert result["status"] == AISuggestionStatus.APPROVED
    assert result["approved_by"] == "consultant@example.com"
    assert result["approved_at"] is not None


async def test_approve_with_edited_payload(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await _seed(db_session, context=context, tenant=tenant)

    edited = {"laeq_db": 87.5, "duration_hours": 3.0, "notes": "corrected"}
    result = await svc.approve(suggestion_id=row.id, tenant_id=tenant.id, edited_payload=edited)
    assert result["payload_json"]["laeq_db"] == 87.5
    assert result["payload_json"]["notes"] == "corrected"
    assert result["status"] == AISuggestionStatus.APPROVED


async def test_approve_already_resolved_raises(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.APPROVED)
    with pytest.raises(InvalidStatusTransitionError):
        await svc.approve(suggestion_id=row.id, tenant_id=tenant.id)


async def test_approve_cross_tenant_raises_not_found(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    other = Tenant(id=uuid.uuid4(), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(other)
    await db_session.flush()
    row = await _seed(db_session, context=context, tenant=other)  # not our tenant

    with pytest.raises(SuggestionNotFoundError):
        await svc.approve(suggestion_id=row.id, tenant_id=tenant.id)


# ── reject ─────────────────────────────────────────────────────────


async def test_reject_with_reason(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await _seed(db_session, context=context, tenant=tenant)

    result = await svc.reject(suggestion_id=row.id, tenant_id=tenant.id, reason="Fase non applicabile")
    assert result["status"] == AISuggestionStatus.REJECTED
    assert result["rejection_reason"] == "Fase non applicabile"


async def test_reject_already_approved_raises(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.APPROVED)
    with pytest.raises(InvalidStatusTransitionError):
        await svc.reject(suggestion_id=row.id, tenant_id=tenant.id)


# ── bulk_action ────────────────────────────────────────────────────


async def test_bulk_approve_all(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    rows = [await _seed(db_session, context=context, tenant=tenant) for _ in range(3)]
    ids = [r.id for r in rows]

    result = await svc.bulk_action(suggestion_ids=ids, tenant_id=tenant.id, action="approve")
    assert result["processed"] == 3
    assert result["total_requested"] == 3
    assert result["failed"] == []


async def test_bulk_approve_filters_by_confidence(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    high = await _seed(db_session, context=context, tenant=tenant, confidence_score=0.9)
    low = await _seed(db_session, context=context, tenant=tenant, confidence_score=0.4)

    result = await svc.bulk_action(
        suggestion_ids=[high.id, low.id],
        tenant_id=tenant.id,
        action="approve",
        min_confidence=0.7,
    )
    assert result["processed"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "below_confidence_threshold"


async def test_bulk_handles_not_found(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    valid = await _seed(db_session, context=context, tenant=tenant)
    bogus = uuid.uuid4()

    result = await svc.bulk_action(suggestion_ids=[valid.id, bogus], tenant_id=tenant.id, action="approve")
    assert result["processed"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "not_found"


async def test_bulk_handles_already_resolved(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    pending = await _seed(db_session, context=context, tenant=tenant)
    already_approved = await _seed(db_session, context=context, tenant=tenant, status=AISuggestionStatus.APPROVED)

    result = await svc.bulk_action(
        suggestion_ids=[pending.id, already_approved.id],
        tenant_id=tenant.id,
        action="approve",
    )
    assert result["processed"] == 1
    assert len(result["failed"]) == 1


# ── serialization shape matches frontend expectation ───────────────


async def test_response_shape_matches_frontend_contract(db_session, tenant, context):
    svc = SuggestionServiceV2(db_session)
    row = await svc.create(
        context_id=context.id,
        tenant_id=tenant.id,
        suggestion_type="phase_laeq",
        title="t",
        payload_json={"x": 1},
        confidence=0.6,
    )
    # Frontend (Wave 29) expects exactly these keys
    expected_keys = {
        "id",
        "tenant_id",
        "context_id",
        "suggestion_type",
        "title",
        "payload_json",
        "confidence",
        "risk_band",
        "priority",
        "status",
        "approved_by",
        "approved_at",
        "rejection_reason",
        "created_at",
        "updated_at",
    }
    assert set(row.keys()) == expected_keys
