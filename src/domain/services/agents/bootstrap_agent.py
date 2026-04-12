"""Bootstrap Agent - AI-guided initial assessment setup."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class BootstrapInput:
    """Input for bootstrap agent."""

    ateco_codes: list[str]
    company_description: str
    existing_data: dict[str, Any] | None = None


@dataclass
class ProcessSuggestion:
    """Suggested work process."""

    name: str
    description: str
    typical_noise_sources: list[str]
    confidence: float


@dataclass
class RoleSuggestion:
    """Suggested job role."""

    name: str
    typical_exposure_hours: float
    processes: list[str]
    confidence: float


@dataclass
class NoiseSourceSuggestion:
    """Suggested noise source."""

    type: str
    typical_noise_level: str
    source_confidence: float


@dataclass
class BootstrapSuggestion:
    """Result of bootstrap operation."""

    processes: list[ProcessSuggestion]
    roles: list[RoleSuggestion]
    noise_sources: list[NoiseSourceSuggestion]
    missing_data: list[str]
    next_actions: list[str]
    confidence_overall: float
    raw_response: dict[str, Any] | None = None


class BootstrapAgent:
    """AI agent for guiding initial noise assessment setup.

    Responsibilities:
    - Analyze ATECO codes to suggest typical processes
    - Query noise source knowledge base
    - Generate role and exposure suggestions
    - Identify missing data
    - Produce actionable next steps
    """

    TEMPLATE_NAME = "bootstrap_prompt.md"

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def suggest(
        self,
        input_data: BootstrapInput,
        assessment_id: UUID | None = None,
    ) -> BootstrapSuggestion:
        """Generate assessment structure suggestions.

        Args:
            input_data: Bootstrap input with ATECO codes and description
            assessment_id: Optional assessment ID for logging

        Returns:
            BootstrapSuggestion with structured recommendations
        """
        # Build context for template
        context = {
            "ateco_codes": ", ".join(input_data.ateco_codes),
            "company_description": input_data.company_description,
            "existing_data": input_data.existing_data or "Nessuno",
        }

        try:
            # Execute AI prompt
            result = await self._orchestrator.execute(
                template_name=self.TEMPLATE_NAME,
                context=context,
                interaction_type="bootstrap",
                assessment_id=assessment_id,
            )

            # Convert to structured suggestions
            return self._parse_suggestions(result)

        except AIOrchestratorError as e:
            logger.error("Bootstrap failed: %s", e)
            return BootstrapSuggestion(
                processes=[],
                roles=[],
                noise_sources=[],
                missing_data=["Errore di connessione AI"],
                next_actions=["Riprovare o verificare configurazione Ollama"],
                confidence_overall=0.0,
                raw_response=None,
            )

    def _parse_suggestions(self, result: dict[str, Any]) -> BootstrapSuggestion:
        """Parse raw AI response into structured suggestions."""
        # Parse processes
        processes = []
        for p in result.get("processi", []):
            processes.append(
                ProcessSuggestion(
                    name=p.get("name", ""),
                    description=p.get("description", ""),
                    typical_noise_sources=p.get("typical_noise_sources", []),
                    confidence=p.get("confidence", 0.5),
                )
            )

        # Parse roles
        roles = []
        for r in result.get("roles", []):
            roles.append(
                RoleSuggestion(
                    name=r.get("name", ""),
                    typical_exposure_hours=r.get("typical_exposure_hours", 8.0),
                    processes=r.get("processes", []),
                    confidence=r.get("confidence", 0.5),
                )
            )

        # Parse noise sources
        noise_sources = []
        for n in result.get("noise_sources", []):
            noise_sources.append(
                NoiseSourceSuggestion(
                    type=n.get("type", ""),
                    typical_noise_level=n.get("typical_noise_level", ""),
                    source_confidence=n.get("source_confidence", 0.5),
                )
            )

        return BootstrapSuggestion(
            processes=processes,
            roles=roles,
            noise_sources=noise_sources,
            missing_data=result.get("missing_data", []),
            next_actions=result.get("next_actions", []),
            confidence_overall=result.get("confidence_overall", 0.5),
            raw_response=result,
        )
