"""Narrative Agent - AI-guided DVR narrative text generation."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class NarrativeSection:
    """A section of the DVR narrative."""

    title: str
    content: str
    data_origin: str


@dataclass
class NarrativeResult:
    """Result of DVR narrative generation."""

    sections: list[NarrativeSection]
    full_text: str
    word_count: int
    confidence: float
    raw_response: dict[str, Any] | None = None


class NarrativeAgent:
    """AI agent for generating Italian DVR document narrative.

    Responsibilities:
    - Generate narrative text following D.Lgs. 81/2008 format
    - Create structured sections: premessa, riferimenti, metodologia, etc.
    - Use Italian technical formal language
    - Distinguish between measured, estimated, and declared data
    """

    TEMPLATE_NAME = "narrative_prompt.md"

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def generate(
        self,
        company_name: str,
        ateco_code: str,
        assessment_date: str,
        responsible_name: str,
        results: dict[str, Any],
        roles: list[dict[str, Any]],
        noise_sources: list[dict[str, Any]],
        mitigations: list[str],
        assessment_id: UUID | None = None,
        section: str | None = None,
    ) -> NarrativeResult:
        """Generate DVR narrative text.

        Args:
            company_name: Name of the company
            ateco_code: ATECO code
            assessment_date: Date of assessment
            responsible_name: Name of responsible person
            results: Calculation results (LEX,8h values)
            roles: List of job roles with exposure data
            noise_sources: List of identified noise sources
            mitigations: List of proposed prevention measures
            assessment_id: Optional assessment ID for logging
            section: Optional specific section to generate

        Returns:
            NarrativeResult with structured narrative sections
        """
        context = {
            "company_name": company_name,
            "ateco_code": ateco_code,
            "assessment_date": assessment_date,
            "responsible_name": responsible_name,
            "results": str(results),
            "roles": str(roles),
            "noise_sources": str(noise_sources),
            "mitigations": ", ".join(mitigations) if mitigations else "Da definire",
            "section": section if section else "Tutti",
        }

        try:
            result = await self._orchestrator.execute(
                template_name=self.TEMPLATE_NAME,
                context=context,
                interaction_type="narrative",
                assessment_id=assessment_id,
            )

            return self._parse_narrative_result(result)

        except AIOrchestratorError as e:
            logger.error("Narrative generation failed: %s", e)
            return NarrativeResult(
                sections=[],
                full_text="Testo narrativo non disponibile a causa di un errore del servizio AI.",
                word_count=0,
                confidence=0.0,
                raw_response=None,
            )

    def _parse_narrative_result(self, result: dict[str, Any]) -> NarrativeResult:
        """Parse raw AI response into structured narrative."""
        sections = []

        for s in result.get("sections", []):
            sections.append(
                NarrativeSection(
                    title=s.get("title", ""),
                    content=s.get("content", ""),
                    data_origin=s.get("data_origin", "Non specificato"),
                )
            )

        full_text = result.get("full_text", "")
        if not full_text and sections:
            full_text = "\n\n".join(f"## {s.title}\n\n{s.content}" for s in sections)

        return NarrativeResult(
            sections=sections,
            full_text=full_text,
            word_count=result.get("word_count", len(full_text.split())),
            confidence=result.get("confidence", 0.5),
            raw_response=result,
        )
