"""Integration tests for AutopilotOrchestrator (pipeline + persistence)."""
from __future__ import annotations

import json
import math
import uuid

import pytest
from sqlalchemy import select

from src.domain.services.autopilot.exposure_estimator import ExposureEstimatorAgent
from src.domain.services.autopilot.iso_9612 import compute_lex_8h, risk_band
from src.domain.services.autopilot.orchestrator import AutopilotOrchestrator
from src.domain.services.autopilot.types import (
    AutopilotEventKind,
    AutopilotRunContext,
    AutopilotStep,
)
from src.domain.services.suggestion_service import SuggestionServiceV2
from src.infrastructure.database.models.ai_suggestion import AISuggestion
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
)
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.llm.mock_provider import MockProvider


# ── ISO 9612 unit tests (pure math, no fixtures) ───────────────────


def test_compute_lex_8h_single_phase_full_shift():
    # 85 dB × 8h → LEX,8h = 85 dB
    result = compute_lex_8h([(85.0, 8.0)])
    assert result == pytest.approx(85.0, abs=0.01)


def test_compute_lex_8h_half_shift_halves_3db():
    # 85 dB × 4h → LEX,8h ≈ 82 dB (halving exposure = −3 dB)
    result = compute_lex_8h([(85.0, 4.0)])
    assert result == pytest.approx(82.0, abs=0.1)


def test_compute_lex_8h_two_phases_sum_correctly():
    # 80 dB × 4h + 90 dB × 4h ≈ 87.4 dB
    result = compute_lex_8h([(80.0, 4.0), (90.0, 4.0)])
    # 10 * log10((4*10^8 + 4*10^9)/8) = 10*log10((4e8+4e9)/8) = 10*log10(5.5e8)
    expected = 10 * math.log10((4 * 10**8 + 4 * 10**9) / 8)
    assert result == pytest.approx(expected, abs=0.01)


def test_compute_lex_8h_empty_returns_zero():
    assert compute_lex_8h([]) == 0.0


def test_risk_band_thresholds():
    assert risk_band(79.9) == "green"
    assert risk_band(80.0) == "yellow"
    assert risk_band(84.9) == "yellow"
    assert risk_band(85.0) == "orange"
    assert risk_band(86.9) == "orange"
    assert risk_band(87.0) == "red"
    assert risk_band(95.0) == "red"


# ── Orchestrator integration tests ─────────────────────────────────


@pytest.fixture
async def seeded(db_session):
    tenant = Tenant(id=uuid.uuid4(), name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()

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
    return tenant, ctx


def _dvr_snapshot_with_phases(n: int = 2) -> dict:
    phases = [
        {"id": f"ph-{i}", "name": f"Phase {i}", "description": f"desc {i}"}
        for i in range(1, n + 1)
    ]
    equipments = [
        {"id": f"eq-{i}", "phaseId": f"ph-{i}", "brand": "Bosch", "model": "X"}
        for i in range(1, n + 1)
    ]
    return {
        "schemaVersion": "1.1.0",
        "companyData": {"vatNumber": "IT0", "legalName": "ACME"},
        "workPhases": phases,
        "phaseEquipments": equipments,
        "risks": [], "actions": [], "trainings": [],
        "module_extensions": {},
    }


def _mock_provider(estimates: list[dict]) -> MockProvider:
    return MockProvider(response_content=json.dumps({"estimates": estimates}))


async def test_pipeline_completes_happy_path(db_session, seeded):
    tenant, ctx_row = seeded

    estimates = [
        {
            "phase_id": "ph-1", "phase_name": "Phase 1", "job_role": "op",
            "laeq_db": 88.0, "duration_hours": 4.0,
            "k_tone_db": 0, "k_imp_db": 0, "confidence": 0.8,
            "reasoning": "ok", "data_gaps": [],
        },
        {
            "phase_id": "ph-2", "phase_name": "Phase 2", "job_role": "op",
            "laeq_db": 92.0, "duration_hours": 2.0,
            "k_tone_db": 3, "k_imp_db": 0, "confidence": 0.7,
            "reasoning": "ok", "data_gaps": [],
        },
    ]
    agent = ExposureEstimatorAgent(_mock_provider(estimates))
    svc = SuggestionServiceV2(db_session)
    orch = AutopilotOrchestrator(db_session, agent, svc)

    run_ctx = AutopilotRunContext(
        context_id=ctx_row.id,
        tenant_id=tenant.id,
        access_token="bearer-x",
        dvr_snapshot=_dvr_snapshot_with_phases(2),
    )

    events = [ev async for ev in orch.run(run_ctx)]

    # Terminates with completed event
    assert events[-1].kind == AutopilotEventKind.completed
    assert events[-1].step == AutopilotStep.done
    assert events[-1].payload["risk_band"] in {"green", "yellow", "orange", "red"}
    assert events[-1].payload["lex_8h_db"] > 0

    # LEX,8h calculated correctly (88+0 dB × 4h + 95 dB × 2h with K_T=3)
    assert run_ctx.lex_8h_db == pytest.approx(
        compute_lex_8h([(88.0, 4.0), (95.0, 2.0)]), abs=0.01
    )

    # All pipeline steps emitted step_completed
    completed_steps = [
        e.step for e in events if e.kind == AutopilotEventKind.step_completed
    ]
    for expected in [
        AutopilotStep.parse_dvr,
        AutopilotStep.source_detection,
        AutopilotStep.exposure_estimation,
        AutopilotStep.iso_9612_calc,
        AutopilotStep.review,
        AutopilotStep.mitigation,
        AutopilotStep.narrative,
        AutopilotStep.persist,
    ]:
        assert expected in completed_steps, f"Missing step_completed for {expected}"

    # Progress monotonic 0..100
    progress_values = [e.progress_percent for e in events if e.progress_percent is not None]
    assert progress_values[0] == 0
    assert progress_values[-1] == 100
    assert all(
        a <= b for a, b in zip(progress_values, progress_values[1:])
    ), "Progress must be monotonic"

    # Suggestions persisted
    result = await db_session.execute(
        select(AISuggestion).where(AISuggestion.context_id == ctx_row.id)
    )
    persisted = result.scalars().all()
    assert len(persisted) == 2
    assert all(p.status == "pending" for p in persisted)
    assert all(p.tenant_id == tenant.id for p in persisted)


async def test_pipeline_with_empty_dvr_still_completes(db_session, seeded):
    tenant, ctx_row = seeded

    agent = ExposureEstimatorAgent(_mock_provider([]))
    svc = SuggestionServiceV2(db_session)
    orch = AutopilotOrchestrator(db_session, agent, svc)

    run_ctx = AutopilotRunContext(
        context_id=ctx_row.id,
        tenant_id=tenant.id,
        access_token="bearer",
        dvr_snapshot={"workPhases": [], "phaseEquipments": []},
    )

    events = [ev async for ev in orch.run(run_ctx)]
    assert events[-1].kind == AutopilotEventKind.completed
    assert run_ctx.lex_8h_db == 0.0
    assert run_ctx.risk_band == "green"


async def test_pipeline_exposure_failure_emits_failed_and_halts(db_session, seeded):
    tenant, ctx_row = seeded

    # MockProvider returning garbage → ExposureEstimatorError
    agent = ExposureEstimatorAgent(MockProvider(response_content="not json"))
    svc = SuggestionServiceV2(db_session)
    orch = AutopilotOrchestrator(db_session, agent, svc)

    run_ctx = AutopilotRunContext(
        context_id=ctx_row.id,
        tenant_id=tenant.id,
        access_token="bearer",
        dvr_snapshot=_dvr_snapshot_with_phases(1),
    )

    events = [ev async for ev in orch.run(run_ctx)]
    kinds = [e.kind for e in events]
    assert AutopilotEventKind.step_failed in kinds
    assert events[-1].kind == AutopilotEventKind.failed

    # No suggestions persisted after failure
    result = await db_session.execute(
        select(AISuggestion).where(AISuggestion.context_id == ctx_row.id)
    )
    assert len(result.scalars().all()) == 0


async def test_pipeline_cancelled_between_stages(db_session, seeded):
    tenant, ctx_row = seeded

    agent = ExposureEstimatorAgent(_mock_provider([
        {
            "phase_id": "ph-1", "phase_name": "P", "laeq_db": 85,
            "duration_hours": 2, "k_tone_db": 0, "k_imp_db": 0,
            "confidence": 0.7, "reasoning": "r", "data_gaps": [],
        }
    ]))
    svc = SuggestionServiceV2(db_session)
    orch = AutopilotOrchestrator(db_session, agent, svc)

    # Cancel immediately
    orch.request_cancel()

    run_ctx = AutopilotRunContext(
        context_id=ctx_row.id,
        tenant_id=tenant.id,
        access_token="bearer",
        dvr_snapshot=_dvr_snapshot_with_phases(1),
    )

    events = [ev async for ev in orch.run(run_ctx)]
    # Should NOT reach the final `completed` event
    assert not any(
        e.kind == AutopilotEventKind.completed and e.step == AutopilotStep.done
        for e in events
    )


async def test_sse_payload_shape_matches_frontend():
    """Frontend AutopilotView expects these keys on each SSE event."""
    from datetime import datetime, timezone
    from src.domain.services.autopilot.types import AutopilotEvent

    ev = AutopilotEvent(
        kind=AutopilotEventKind.step_completed,
        step=AutopilotStep.exposure_estimation,
        message="done",
        payload={"estimates_count": 3},
        progress_percent=45,
        timestamp=datetime.now(timezone.utc),
    )
    d = ev.to_sse_dict()
    assert d["kind"] == "step_completed"
    assert d["step"] == "exposure_estimation"
    assert d["message"] == "done"
    assert d["payload"]["estimates_count"] == 3
    assert d["progress_percent"] == 45
    assert "timestamp" in d
