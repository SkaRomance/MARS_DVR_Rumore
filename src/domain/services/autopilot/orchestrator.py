"""AutopilotOrchestrator — runs the AI pipeline as an async event stream.

Pipeline stages (v1 — all stages now backed by real agents marked ★):
  1. initialize
  2. parse_dvr              ★  extract PhaseInput[] from snapshot
  3. source_detection          (stub — future PAF matching)
  4. exposure_estimation    ★  ExposureEstimatorAgent
  5. iso_9612_calc          ★  LEX,8h + risk band
  6. review                 ★  ReviewAgent (cross-validation)
  7. mitigation             ★  MitigationAgent (Art. 192 hierarchy)
  8. narrative              ★  NarrativeAgent (DVR paragraph)
  9. persist                ★  create AISuggestion rows
  10. done

Each stage emits started → completed | failed events. The `run()` method
is an async generator yielding AutopilotEvent objects as work progresses.
A cancellation token (`request_cancel()`) aborts between stages.

Error handling policy (applies to review/mitigation/narrative):
  These three stages are "enrichment" steps — not blockers. Unlike
  ExposureEstimator's halt-on-failure pattern, a failure here leaves the
  core value (LEX,8h + risk band) intact. Policy: on typed agent error
  we emit `step_failed` (non-fatal), log a warning, leave the run_ctx
  field empty/None, and continue. The exposure_estimation step remains
  fatal. Unexpected (non-typed) exceptions still fall through to the
  top-level except and halt the pipeline.
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
from src.domain.services.autopilot.mitigation_agent import (
    MitigationAgent,
    MitigationAgentError,
)
from src.domain.services.autopilot.narrative_agent import (
    NarrativeAgent,
    NarrativeAgentError,
)
from src.domain.services.autopilot.review_agent import (
    ReviewAgent,
    ReviewAgentError,
)
from src.domain.services.autopilot.types import (
    AutopilotEvent,
    AutopilotEventKind,
    AutopilotRunContext,
    AutopilotStep,
    MitigationSuggestion,
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
        *,
        review_agent: ReviewAgent | None = None,
        mitigation_agent: MitigationAgent | None = None,
        narrative_agent: NarrativeAgent | None = None,
    ):
        self._session = session
        self._exposure_agent = exposure_agent
        self._suggestion_service = suggestion_service
        # Review/mitigation/narrative are optional: when None, the step
        # still emits step_completed with an empty payload (backward-
        # compatible with callers that have not yet wired the agents).
        self._review_agent = review_agent
        self._mitigation_agent = mitigation_agent
        self._narrative_agent = narrative_agent
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

            # ── review (real) ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.review,
                progress,
                message="Validazione incrociata delle stime",
            )
            if self._review_agent is not None:
                try:
                    ctx.review_findings = await self._review_agent.review(ctx.exposure_estimates)
                except ReviewAgentError as exc:
                    # Non-fatal: pipeline continues with empty findings.
                    logger.warning("Review agent failed: %s", exc)
                    ctx.review_findings = []
                    yield self._event(
                        AutopilotEventKind.step_failed,
                        AutopilotStep.review,
                        progress,
                        message=f"Review agent failed (non-fatal): {exc}",
                    )
            progress += _STEP_WEIGHTS[AutopilotStep.review]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.review,
                progress,
                payload={"findings_count": len(ctx.review_findings)},
            )
            if self._check_cancel():
                return

            # ── mitigation (real) ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.mitigation,
                progress,
                message="Misure di mitigazione (D.Lgs. 81/2008 Art. 192)",
            )
            if self._mitigation_agent is not None:
                try:
                    ctx.mitigation_suggestions = await self._mitigation_agent.suggest(
                        ctx.exposure_estimates,
                        ctx.lex_8h_db or 0.0,
                    )
                except MitigationAgentError as exc:
                    logger.warning("Mitigation agent failed: %s", exc)
                    ctx.mitigation_suggestions = []
                    yield self._event(
                        AutopilotEventKind.step_failed,
                        AutopilotStep.mitigation,
                        progress,
                        message=f"Mitigation agent failed (non-fatal): {exc}",
                    )
            progress += _STEP_WEIGHTS[AutopilotStep.mitigation]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.mitigation,
                progress,
                payload={"suggestions_count": len(ctx.mitigation_suggestions)},
            )
            if self._check_cancel():
                return

            # ── narrative (real) ──
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.narrative,
                progress,
                message="Generazione narrativa DVR",
            )
            if self._narrative_agent is not None and ctx.exposure_estimates:
                try:
                    ctx.narrative_text = await self._narrative_agent.generate(
                        ctx.lex_8h_db or 0.0,
                        ctx.risk_band or "green",
                        ctx.exposure_estimates,
                        ctx.review_findings,
                    )
                except NarrativeAgentError as exc:
                    logger.warning("Narrative agent failed: %s", exc)
                    ctx.narrative_text = None
                    yield self._event(
                        AutopilotEventKind.step_failed,
                        AutopilotStep.narrative,
                        progress,
                        message=f"Narrative agent failed (non-fatal): {exc}",
                    )
            progress += _STEP_WEIGHTS[AutopilotStep.narrative]
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.narrative,
                progress,
                payload={
                    "narrative_generated": ctx.narrative_text is not None,
                    "narrative_chars": len(ctx.narrative_text) if ctx.narrative_text else 0,
                },
            )
            if self._check_cancel():
                return

            # ── persist ──
            # Persists: exposure estimates (phase_laeq suggestions) + mitigation
            # suggestions (suggestion_type="mitigation"). narrative_text is NOT
            # persisted because adding a column to NoiseAssessmentContext would
            # require a migration; it lives in run_ctx in-memory only for now
            # (future wave: persist to a dedicated field or separate table).
            yield self._event(
                AutopilotEventKind.step_started,
                AutopilotStep.persist,
                progress,
                message="Salvataggio suggerimenti",
            )
            persisted = await self._persist_estimates(ctx)
            mitigation_ids = await self._persist_mitigations(ctx)
            ctx.persisted_suggestion_ids = persisted + mitigation_ids
            progress = 100
            yield self._event(
                AutopilotEventKind.step_completed,
                AutopilotStep.persist,
                progress,
                payload={
                    "suggestions_count": len(persisted),
                    "mitigations_count": len(mitigation_ids),
                },
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
                    "mitigations_count": len(mitigation_ids),
                    "findings_count": len(ctx.review_findings),
                    "narrative_chars": len(ctx.narrative_text) if ctx.narrative_text else 0,
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

    async def _persist_mitigations(self, ctx: AutopilotRunContext) -> list[uuid.UUID]:
        """Write mitigation suggestions as pending AISuggestion rows."""
        ids: list[uuid.UUID] = []
        for sug in ctx.mitigation_suggestions:
            payload = self._mitigation_to_payload(sug)
            result = await self._suggestion_service.create(
                context_id=ctx.context_id,
                tenant_id=ctx.tenant_id,
                suggestion_type="mitigation",
                title=self._mitigation_title(sug),
                payload_json=payload,
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
    def _mitigation_title(sug: MitigationSuggestion) -> str:
        cat_label = {
            "technical": "Tecnica",
            "organizational": "Organizzativa",
            "ppe": "DPI",
        }.get(sug.category, sug.category)
        measure_short = sug.measure[:80] + ("…" if len(sug.measure) > 80 else "")
        return f"[{cat_label}] {measure_short}"

    @staticmethod
    def _mitigation_to_payload(sug: MitigationSuggestion) -> dict:
        return {
            "phase_id": sug.phase_id,
            "category": sug.category,
            "measure": sug.measure,
            "expected_reduction_db": sug.expected_reduction_db,
            "reasoning": sug.reasoning,
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
