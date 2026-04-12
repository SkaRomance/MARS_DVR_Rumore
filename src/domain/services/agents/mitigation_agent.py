"""Mitigation Agent - AI-guided risk mitigation suggestions."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class EngineeringControl:
    """Engineering control measure."""

    type: str
    description: str
    estimated_effectiveness: float | None
    estimated_cost: str | None
    priority: int


@dataclass
class AdministrativeControl:
    """Administrative control measure."""

    type: str
    description: str
    estimated_effectiveness: float | None
    priority: int


@dataclass
class PPERecommendation:
    """PPE recommendation."""

    type: str
    nrr: int | None
    description: str
    suitable_for: list[str]
    priority: int


@dataclass
class MitigationResult:
    """Result of mitigation suggestion."""

    engineer_controls: list[EngineeringControl]
    administrative_controls: list[AdministrativeControl]
    ppe_recommendations: list[PPERecommendation]
    priority_order: list[str]
    overall_risk_reduction: str | None
    confidence: float
    raw_response: dict[str, Any] | None = None


class MitigationAgent:
    """AI agent for suggesting risk mitigation measures.

    Responsibilities:
    - Suggest engineering controls (controlli ingegneristici)
    - Suggest administrative controls (controlli amministrativi)
    - Recommend PPE (dispositivi di protezione individuale)
    - Follow Italian D.Lgs. 81/2008 hierarchy (art. 195)
    - Prioritize measures by effectiveness and feasibility
    """

    TEMPLATE_NAME = "mitigation_prompt.md"

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def suggest(
        self,
        lex_levels: dict[str, float],
        risk_bands: dict[str, str],
        affected_roles: list[str] | None = None,
        assessment_id: UUID | None = None,
        include_ppe: bool = True,
        include_engineering: bool = True,
        include_administrative: bool = True,
    ) -> MitigationResult:
        """Suggest mitigation measures based on risk levels.

        Args:
            lex_levels: Map of role -> LEX,8h level
            risk_bands: Map of role -> risk band (negligible/low/medium/high)
            affected_roles: List of roles at risk
            assessment_id: Optional assessment ID for logging
            include_ppe: Include PPE recommendations
            include_engineering: Include engineering controls
            include_administrative: Include administrative controls

        Returns:
            MitigationResult with structured mitigation suggestions
        """
        context = {
            "lex_levels": str(lex_levels),
            "risk_bands": str(risk_bands),
            "affected_roles": ", ".join(affected_roles) if affected_roles else "Tutti",
            "include_ppe": str(include_ppe),
            "include_engineering": str(include_engineering),
            "include_administrative": str(include_administrative),
        }

        try:
            result = await self._orchestrator.execute(
                template_name=self.TEMPLATE_NAME,
                context=context,
                interaction_type="mitigation",
                assessment_id=assessment_id,
            )

            return self._parse_mitigation_result(result)

        except AIOrchestratorError as e:
            logger.error("Mitigation suggestion failed: %s", e)
            return MitigationResult(
                engineer_controls=[],
                administrative_controls=[],
                ppe_recommendations=[],
                priority_order=[],
                overall_risk_reduction=None,
                confidence=0.0,
                raw_response=None,
            )

    def _parse_mitigation_result(self, result: dict[str, Any]) -> MitigationResult:
        """Parse raw AI response into structured mitigation results."""
        engineer_controls = []
        for c in result.get("engineer_controls", []):
            engineer_controls.append(
                EngineeringControl(
                    type=c.get("type", ""),
                    description=c.get("description", ""),
                    estimated_effectiveness=c.get("estimated_effectiveness"),
                    estimated_cost=c.get("estimated_cost"),
                    priority=c.get("priority", 1),
                )
            )

        administrative_controls = []
        for c in result.get("administrative_controls", []):
            administrative_controls.append(
                AdministrativeControl(
                    type=c.get("type", ""),
                    description=c.get("description", ""),
                    estimated_effectiveness=c.get("estimated_effectiveness"),
                    priority=c.get("priority", 2),
                )
            )

        ppe_recommendations = []
        for p in result.get("ppe_recommendations", []):
            ppe_recommendations.append(
                PPERecommendation(
                    type=p.get("type", ""),
                    nrr=p.get("nrr"),
                    description=p.get("description", ""),
                    suitable_for=p.get("suitable_for", []),
                    priority=p.get("priority", 3),
                )
            )

        return MitigationResult(
            engineer_controls=engineer_controls,
            administrative_controls=administrative_controls,
            ppe_recommendations=ppe_recommendations,
            priority_order=result.get("priority_order", []),
            overall_risk_reduction=result.get("overall_risk_reduction"),
            confidence=result.get("confidence", 0.5),
            raw_response=result,
        )
