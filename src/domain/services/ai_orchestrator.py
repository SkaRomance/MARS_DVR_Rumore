"""AI Orchestrator - Coordinates LLM calls, templates, and interaction logging."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from src.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse
from src.domain.services.prompts.template_loader import (
    get_template_loader,
    TemplateLoader,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for AI orchestrator."""

    max_retries: int = 2
    timeout_seconds: float = 120.0
    cache_enabled: bool = True


class AIOrchestrator:
    """Coordinates AI interactions for noise assessment.

    Responsibilities:
    - Load and render prompt templates
    - Call LLM provider with structured prompts
    - Parse and validate JSON responses
    - Log interactions to database
    - Handle errors gracefully
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        template_loader: TemplateLoader | None = None,
        config: OrchestratorConfig | None = None,
    ):
        self._provider = llm_provider
        self._templates = template_loader or get_template_loader()
        self._config = config or OrchestratorConfig()
        self._cache: dict[str, LLMResponse] = {}

    async def execute(
        self,
        template_name: str,
        context: dict[str, Any],
        interaction_type: str,
        assessment_id: UUID | None = None,
        store_interaction: bool = True,
    ) -> dict[str, Any]:
        """Execute an AI prompt and return structured response.

        Args:
            template_name: Name of prompt template
            context: Variables for template rendering
            interaction_type: Type of interaction (bootstrap, review, etc.)
            assessment_id: Optional assessment ID for logging
            store_interaction: Whether to log to database

        Returns:
            Parsed JSON response from LLM

        Raises:
            AIOrchestratorError: If execution fails
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(interaction_type)

        # Render template
        user_prompt = self._templates.render(template_name, context)

        # Check cache if enabled
        cache_key = f"{template_name}:{hash(user_prompt)}"
        if self._config.cache_enabled and cache_key in self._cache:
            logger.info("Using cached response for %s", template_name)
            response = self._cache[cache_key]
        else:
            # Create request
            request = LLMRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=750,
                temperature=0.3,
            )

            # Call LLM with retries
            response = await self._call_with_retries(request)

            # Cache if enabled
            if self._config.cache_enabled:
                self._cache[cache_key] = response

        # Parse response
        try:
            result = self._parse_json_response(response.content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON, returning raw content: %s", e)
            result = {"raw_content": response.content, "parse_error": str(e)}

        # Log interaction (if db session provided via context)
        if store_interaction and "db_session" in context:
            await self._log_interaction(
                session=context["db_session"],
                interaction_type=interaction_type,
                prompt=user_prompt,
                response=response.content,
                model_name=response.model,
                tokens_used=response.tokens_used,
                assessment_id=assessment_id,
            )

        return result

    def _build_system_prompt(self, interaction_type: str) -> str:
        """Build system prompt based on interaction type."""
        base = "Sei un esperto consulente HSE italiano in valutazione rischio rumore (D.Lgs. 81/2008)."

        prompts = {
            "bootstrap": f"{base} Aiuti a impostare nuove valutazioni del rumore.",
            "review": f"{base} Verifichi e revisioni valutazioni esistenti.",
            "narrative": f"{base} Generi testi tecnici per documenti DVR.",
            "explain": f"{base} Spieghi concetti tecnici in modo chiaro.",
            "mitigation": f"{base} Suggerisci misure di prevenzione e protezione.",
            "source_detection": f"{base} Identifichi sorgenti di rumore da descrizioni.",
        }

        return prompts.get(interaction_type, base)

    async def _call_with_retries(self, request: LLMRequest) -> LLMResponse:
        """Call LLM with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                return await self._provider.generate(request)
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call failed (attempt %s/%s): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    e,
                )

        raise AIOrchestratorError(
            f"LLM call failed after {self._config.max_retries} retries: {last_error}"
        )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()
        return json.loads(content)

    async def _log_interaction(
        self,
        session: Any,
        interaction_type: str,
        prompt: str,
        response: str,
        model_name: str,
        tokens_used: int,
        assessment_id: UUID | None,
    ):
        """Log interaction to database."""
        try:
            from src.infrastructure.database.models import AIInteraction

            interaction = AIInteraction(
                assessment_id=assessment_id,
                interaction_type=interaction_type,
                prompt=prompt[:10000],  # Truncate if too long
                response=response[:10000],
                model_name=model_name,
                tokens_used=tokens_used,
            )
            session.add(interaction)
            await session.commit()
        except Exception as e:
            logger.error("Failed to log AI interaction: %s", e)


class AIOrchestratorError(Exception):
    """Error raised by AI orchestrator."""

    pass
