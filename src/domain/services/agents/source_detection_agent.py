"""Source Detection Agent - Identifies noise sources from text descriptions."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class DetectedSource:
    """A detected noise source."""

    type: str
    description: str
    typical_noise_level: str
    confidence: float
    source_match: str | None = None


@dataclass
class SourceDetectionResult:
    """Result from source detection."""

    detected_sources: list[DetectedSource]
    confidence_overall: float
    processing_notes: str | None = None


class SourceDetectionAgent:
    """Agent for detecting noise sources from free-text descriptions.

    Matches descriptions to known noise source types and suggests
    typical noise levels based on PAF (Portale Agenti Fisici) data.
    """

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def detect(
        self,
        description: str,
        assessment_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> SourceDetectionResult:
        """Detect noise sources from a text description.

        Args:
            description: Free-text description of work activities or environment
            assessment_id: Optional assessment ID for logging
            context: Optional additional context (company type, industry, etc.)

        Returns:
            SourceDetectionResult with detected sources and confidence
        """
        context = context or {}

        try:
            result = await self._orchestrator.execute(
                template_name="source_detection_prompt.md",
                context={
                    "description": description,
                    "company_type": context.get("company_type", "manifatturiero"),
                    "assessment_id": str(assessment_id) if assessment_id else "",
                },
                interaction_type="source_detection",
                assessment_id=assessment_id,
                store_interaction=True,
            )

            return self._parse_result(result)

        except AIOrchestratorError as e:
            logger.error("Source detection failed: %s", e)
            raise

    def _parse_result(self, result: dict[str, Any]) -> SourceDetectionResult:
        """Parse LLM JSON response into SourceDetectionResult."""
        detected_sources = []

        for source_data in result.get("sources", []):
            detected_sources.append(
                DetectedSource(
                    type=source_data.get("type", "Sconosciuto"),
                    description=source_data.get("description", ""),
                    typical_noise_level=source_data.get("noise_level", "N/D"),
                    confidence=source_data.get("confidence", 0.5),
                    source_match=source_data.get("source_match"),
                )
            )

        return SourceDetectionResult(
            detected_sources=detected_sources,
            confidence_overall=result.get("confidence", 0.5),
            processing_notes=result.get("notes"),
        )
