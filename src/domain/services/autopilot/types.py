"""Shared types for the AI Autopilot pipeline."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class PhaseInput:
    """Input to exposure estimation: a work phase + associated equipment."""

    phase_id: str
    phase_name: str
    description: str | None = None
    equipments: list[dict[str, Any]] = field(default_factory=list)
    job_role: str | None = None


@dataclass(frozen=True)
class PhaseExposureEstimate:
    """LLM-estimated noise exposure for a single phase/role combination."""

    phase_id: str
    phase_name: str
    job_role: str | None
    laeq_db: float
    duration_hours: float
    lcpeak_db: float | None
    k_tone_db: float  # 0/3/6 per ISO 9612
    k_imp_db: float  # 0/3/6
    confidence: float  # 0.0-1.0
    reasoning: str
    data_gaps: list[str]
    source: Literal["paf_catalog", "estimated", "llm_inferred"] = "llm_inferred"


@dataclass(frozen=True)
class ReviewFinding:
    """A single finding from ReviewAgent: outlier/low-confidence/data-gap signal."""

    phase_id: str
    severity: Literal["info", "warning", "error"]
    issue: str
    recommendation: str


@dataclass(frozen=True)
class MitigationSuggestion:
    """A single mitigation measure proposed for a risky phase (>=80 dB)."""

    phase_id: str
    category: Literal["technical", "organizational", "ppe"]
    measure: str
    expected_reduction_db: float | None
    reasoning: str


class AutopilotEventKind(enum.StrEnum):
    """SSE event kinds emitted by the orchestrator."""

    started = "started"
    step_started = "step_started"
    step_completed = "step_completed"
    step_failed = "step_failed"
    progress = "progress"
    completed = "completed"
    failed = "failed"


class AutopilotStep(enum.StrEnum):
    """Pipeline step identifiers — ordered roughly by execution."""

    initialize = "initialize"
    parse_dvr = "parse_dvr"
    source_detection = "source_detection"
    exposure_estimation = "exposure_estimation"
    iso_9612_calc = "iso_9612_calc"
    review = "review"
    mitigation = "mitigation"
    narrative = "narrative"
    persist = "persist"
    done = "done"


@dataclass(frozen=True)
class AutopilotEvent:
    """One event in the autopilot SSE stream."""

    kind: AutopilotEventKind
    step: AutopilotStep
    message: str | None = None
    payload: dict[str, Any] | None = None
    progress_percent: int | None = None  # 0..100
    timestamp: datetime | None = None

    def to_sse_dict(self) -> dict[str, Any]:
        """Serialize as the JSON frontend consumes in the SSE handler."""
        return {
            "kind": self.kind.value,
            "step": self.step.value,
            "message": self.message,
            "payload": self.payload or {},
            "progress_percent": self.progress_percent,
            "timestamp": (self.timestamp or datetime.utcnow()).isoformat(),
        }


@dataclass
class AutopilotRunContext:
    """Mutable context threaded through the pipeline."""

    context_id: uuid.UUID
    tenant_id: uuid.UUID
    access_token: str
    dvr_snapshot: dict[str, Any]
    # Populated as the pipeline progresses
    phase_inputs: list[PhaseInput] = field(default_factory=list)
    exposure_estimates: list[PhaseExposureEstimate] = field(default_factory=list)
    lex_8h_db: float | None = None
    risk_band: Literal["green", "yellow", "orange", "red"] | None = None
    review_findings: list[ReviewFinding] = field(default_factory=list)
    mitigation_suggestions: list[MitigationSuggestion] = field(default_factory=list)
    narrative_text: str | None = None
    persisted_suggestion_ids: list[uuid.UUID] = field(default_factory=list)
