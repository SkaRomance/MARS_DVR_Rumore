"""AutopilotOrchestrator — runs the AI pipeline as an async event stream.

Pipeline stages (v1 — real stages marked ★, others are stubs):
  1. initialize
  2. parse_dvr              ★  extract PhaseInput[] from snapshot
  3. source_detection          (stub — future PAF matching)
  4. exposure_estimation    ★  ExposureEstimatorAgent
  5. iso_9612_calc          ★  LEX,8h + risk band
  6. review                    (stub — future cross-validation agent)
  7. mitigation                (stub — future mitigation agent)
  8. narrative                 (stub — future narrative generator)
  9. persist                ★  create AISuggestion rows
  10. done

Each stage emits started → completed | failed events. The `run()` method
is an async generator yielding AutopilotEvent objects as work progresses.
A cancellation token (`request_cancel()`) aborts between stages.

This is the skeleton; future stages get filled in by plugging in agents
at the marked positions without touching the SSE wiring.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.autopilot.exposure_estimator import (
    ExposureEstimatorAgent,
    ExposureEstimatorError,
)
from src.domain.services.autopilot.iso_9612 import (
    compute_lex_8h_from_estimates,
    risk_band,
)
from src.domain.services.autopilot.types import (
    AutopilotEvent,
    AutopilotEventKind,
    AutopilotRunContext,
    AutopilotStep,
    PhaseExposureEstimate,
    PhaseInput,
)
from src.domain.services.suggestion_service import SuggestionServiceV2

logger = logging.getLogger(__name__)


_STEP_WEIGHTS = {
    AutopilotStep.initialize: 5,
    AutopilotStep.parse_dvr: 10,
    AutopilotStep.source_detection: 10,
    AutopilotStep.exposure_estimation: 35,  # LLM-heavy, longest
    AutopilotStep.iso_9612_calc: 5,
    AutopilotStep.review: 10,
    AutopilotStep.mitigation: 10,
    AutopilotStep.narrative: 10,
    AutopilotStep.persist: 5,
}


class AutopilotOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        exposure_agent: ExposureEstimatorAgent,
        suggestion_service: SuggestionServiceV2,
    ):
        self._session = session
        self._exposure_agent = exposure_agent
        self._suggestion_service = suggestion_service
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    async def run(self, ctx: AutopilotRunContext) -> AsyncGenerator[AutopilotEvent, None]:
        start_ts = datetime.now(UTC)
        progress = 0
        yield self._event(AutopilotEventKind.started, AutopilotStep.initialize, progress)

        try:
            # ── parse_dvr ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.parse_dvr,
                progress,
                message="Estrazione fasi e macchinari dal DVR",
            )
            ctx.phase_inputs = self._parse_dvr(ctx.dvr_snapshot)
            progress += _STEP_WEIGHTS[AutopilotStep.parse_dvr]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.parse_dvr,
                progress,
                payload={"phases_count": len(ctx.phase_inputs)},
            )
            if self._check_cancel():
                return

            # ── source_detection (stub) ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.source_detection,
                progress,
                message="Identificazione sorgenti rumorose (PAF catalog — stub)",
            )
            progress += _STEP_WEIGHTS[AutopilotStep.source_detection]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.source_detection,
                progress,
                payload={"candidates_count": 0, "note": "PAF matching pending (Wave 28)"},
            )
            if self._check_cancel():
                return

            # ── exposure_estimation (real) ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.exposure_estimation,
                progress,
                message="Stima LAeq + durata per fase",
            )
            try:
                ctx.exposure_estimates = await self._exposure_agent.estimate(ctx.phase_inputs)
            except ExposureEstimatorError as exc:
                yield self._event(
                    AutopilotEventKind.step_failed,
                    AutopilotStep.exposure_estimation,
                    progress,
                    message=str(exc),
                )
                yield self._event(
                    AutopilotEventKind.failed,
                    AutopilotStep.exposure_estimation,
                    progress,
                    message="Exposure estimation failed; pipeline halted",
                    payload={"failed_step": AutopilotStep.exposure_estimation.value},
                )
                return
            progress += _STEP_WEIGHTS[AutopilotStep.exposure_estimation]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.exposure_estimation,
                progress,
                payload={"estimates_count": len(ctx.exposure_estimates)},
            )
            if self._check_cancel():
                return

            # ── iso_9612_calc ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.iso_9612_calc,
                progress,
                message="Calcolo LEX,8h + banda di rischio",
            )
            if ctx.exposure_estimates:
                ctx.lex_8h_db = compute_lex_8h_from_estimates(ctx.exposure_estimates)
                ctx.risk_band = risk_band(ctx.lex_8h_db)
            else:
                ctx.lex_8h_db = 0.0
                ctx.risk_band = "green"
            progress += _STEP_WEIGHTS[AutopilotStep.iso_9612_calc]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.iso_9612_calc,
                progress,
                payload={
                    "lex_8h_db": round(ctx.lex_8h_db, 2),
                    "risk_band": ctx.risk_band,
                },
            )
            if self._check_cancel():
                return

            # ── review (stub) ──
            for step_stub, label in [
                (AutopilotStep.review, "Validazione incrociata (stub)"),
                (AutopilotStep.mitigation, "Misure di mitigazione (stub)"),
                (AutopilotStep.narrative, "Generazione narrativa DVR (stub)"),
            ]:
                yield self._event(
                    AutopilotEventKind.step_started,
                    step_stub,
                    progress,
                    message=label,
                )
                progress += _STEP_WEIGHTS[step_stub]
                yield self._event(
                    AutopilotEventKind.step_completed,
                    step_stub,
                    progress,
                    payload={"note": f"{step_stub.value} pending future wave"},
                )
                if self._check_cancel():
                    return

            # ── persist ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.persist,
                progress,
                message="Salvataggio suggerimenti",
            )
            persisted = await self._persist_estimates(ctx)
            ctx.persisted_suggestion_ids = persisted
            progress = 100
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.persist,
                progress,
                payload={"suggestions_count": len(persisted)},
            )

            # ── done ──
            duration_s = (datetime.now(UTC) - start_ts).total_seconds()
            confidence = sum(e.confidence for e in ctx.exposure_estimates) / max(len(ctx.exposure_estimates), 1)
            yield self._event(
                AutopilotEventKind.completed,
                AutopilotStep.done,
                100,
                message="Valutazione completata",
                payload={
                    "lex_8h_db": round(ctx.lex_8h_db or 0, 2),
                    "risk_band": ctx.risk_band,
                    "confidence": round(confidence, 2),
                    "duration_s": round(duration_s, 2),
                    "suggestions_count": len(persisted),
                    "estimates_count": len(ctx.exposure_estimates),
                },
            )
        except Exception as exc:  # noqa: BLE001 — last-resort safety net
            logger.exception("Autopilot crashed unexpectedly")
            yield self._event(
                AutopilotEventKind.failed,
                AutopilotStep.done,
                progress,
                message=f"Unexpected error: {exc}",
            )

    # ── internal helpers ───────────────────────────────────────────

    def _check_cancel(self) -> bool:
        return self._cancelled

    @staticmethod
    def _parse_dvr(snapshot: dict) -> list[PhaseInput]:
        """Extract PhaseInput list from DVR snapshot (v1.0 or v1.1)."""
        phases_raw = snapshot.get("workPhases") or snapshot.get("work_phases") or []
        equipments_raw = snapshot.get("phaseEquipments") or snapshot.get("phase_equipments") or []
        # Group equipments by phase_id for efficient lookup
        equipments_by_phase: dict[str, list[dict]] = {}
        for eq in equipments_raw:
            pid = eq.get("phaseId") or eq.get("phase_id")
            if pid is None:
                continue
            equipments_by_phase.setdefault(pid, []).append(eq)

        inputs: list[PhaseInput] = []
        for ph in phases_raw:
            phase_id = ph.get("id") or ""
            inputs.append(
                PhaseInput(
                    phase_id=phase_id,
                    phase_name=ph.get("name", "Unnamed phase"),
                    description=ph.get("description"),
                    equipments=equipments_by_phase.get(phase_id, []),
                    job_role=ph.get("jobRole") or ph.get("job_role"),
                )
            )
        return inputs

    async def _persist_estimates(self, ctx: AutopilotRunContext) -> list[uuid.UUID]:
        """Write exposure estimates as pending AISuggestion rows."""
        ids: list[uuid.UUID] = []
        for est in ctx.exposure_estimates:
            payload = self._estimate_to_payload(est)
            result = await self._suggestion_service.create(
                context_id=ctx.context_id,
                tenant_id=ctx.tenant_id,
                suggestion_type="phase_laeq",
                title=self._estimate_title(est),
                payload_json=payload,
                confidence=est.confidence,
                risk_band=ctx.risk_band,
            )
            ids.append(uuid.UUID(result["id"]))
        return ids

    @staticmethod
    def _estimate_title(est: PhaseExposureEstimate) -> str:
        band_icon = {
            "green": "",
            "yellow": "⚠ ",
            "orange": "⚠⚠ ",
            "red": "🔴 ",
        }.get("green", "")
        return (
            f"{band_icon}{est.phase_name}"
            f"{f' — {est.job_role}' if est.job_role else ''}: "
            f"{est.laeq_db:.1f} dB × {est.duration_hours:.1f}h"
        )

    @staticmethod
    def _estimate_to_payload(est: PhaseExposureEstimate) -> dict:
        return {
            "phase_id": est.phase_id,
            "phase_name": est.phase_name,
            "job_role": est.job_role,
            "laeq_db": est.laeq_db,
            "duration_hours": est.duration_hours,
            "lcpeak_db": est.lcpeak_db,
            "k_corrections": {
                "k_tone": est.k_tone_db,
                "k_imp": est.k_imp_db,
            },
            "reasoning": est.reasoning,
            "data_gaps": list(est.data_gaps),
            "source": est.source,
        }

    @staticmethod
    def _event(
        kind: AutopilotEventKind,
        step: AutopilotStep,
        progress: int,
        *,
        message: str | None = None,
        payload: dict | None = None,
    ) -> AutopilotEvent:
        return AutopilotEvent(
            kind=kind,
            step=step,
            message=message,
            payload=payload,
            progress_percent=max(0, min(100, progress)),
            timestamp=datetime.now(UTC),
        )
