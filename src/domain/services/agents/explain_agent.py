"""Explain Agent - AI-guided technical explanations."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class TechnicalDetails:
    """Technical details for explanation."""

    formulas: list[str]
    references: list[str]
    values: dict[str, Any]


@dataclass
class ExplainResult:
    """Result of explanation generation."""

    explanation: str
    technical_details: TechnicalDetails | None
    related_regulations: list[str]
    confidence: float
    raw_response: dict[str, Any] | None = None


class ExplainAgent:
    """AI agent for generating technical explanations.

    Responsibilities:
    - Generate explanations at three levels (beginner, technical, expert)
    - Cover topics: lex_calculation, risk_band, threshold, mitigation
    - Provide technical details, formulas, and references
    """

    TEMPLATE_NAME = "explain_prompt.md"
    VALID_LEVELS = ["beginner", "technical", "expert"]
    VALID_SUBJECTS = ["lex_calculation", "risk_band", "threshold", "mitigation"]

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def explain(
        self,
        subject: str,
        level: str,
        context_data: dict[str, Any],
        assessment_id: UUID | None = None,
        target_id: UUID | None = None,
    ) -> ExplainResult:
        """Generate explanation for a subject.

        Args:
            subject: Topic to explain (lex_calculation, risk_band, threshold, mitigation)
            level: Detail level (beginner, technical, expert)
            context_data: Contextual data for the explanation
            assessment_id: Optional assessment ID for logging
            target_id: Optional specific element ID

        Returns:
            ExplainResult with structured explanation
        """
        if level not in self.VALID_LEVELS:
            level = "technical"
        if subject not in self.VALID_SUBJECTS:
            subject = "lex_calculation"

        context = {
            "subject": subject,
            "level": level,
            "context_data": str(context_data),
            "target_id": str(target_id) if target_id else "Generico",
        }

        try:
            result = await self._orchestrator.execute(
                template_name=self.TEMPLATE_NAME,
                context=context,
                interaction_type="explain",
                assessment_id=assessment_id,
            )

            return self._parse_explain_result(result)

        except AIOrchestratorError as e:
            logger.error("Explain failed: %s", e)
            return ExplainResult(
                explanation="Spiegazione non disponibile a causa di un errore del servizio AI.",
                technical_details=None,
                related_regulations=["D.Lgs. 81/2008"],
                confidence=0.0,
                raw_response=None,
            )

    def _parse_explain_result(self, result: dict[str, Any]) -> ExplainResult:
        """Parse raw AI response into structured explanation."""
        technical_details = None
        if "technical_details" in result:
            td = result["technical_details"]
            technical_details = TechnicalDetails(
                formulas=td.get("formulas", []),
                references=td.get("references", []),
                values=td.get("values", {}),
            )

        return ExplainResult(
            explanation=result.get("explanation", ""),
            technical_details=technical_details,
            related_regulations=result.get("related_regulations", []),
            confidence=result.get("confidence", 0.5),
            raw_response=result,
        )
