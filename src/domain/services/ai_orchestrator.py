"""AI Orchestrator - Coordinates LLM calls, templates, RAG context, and interaction logging."""

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.prompts.template_loader import (
    TemplateLoader,
    get_template_loader,
)
from src.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for AI orchestrator."""

    max_retries: int = 2
    timeout_seconds: float = 120.0
    cache_enabled: bool = True
    rag_enabled: bool = True
    rag_n_results: int = 5
    rag_max_context_chars: int = 4000


class AIOrchestrator:
    """Coordinates AI interactions for noise assessment.

    Responsibilities:
    - Load and render prompt templates
    -Retrieve relevant documents via RAG
    - Inject RAG context into prompts
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
        self._rag_service = None

    def _get_rag_service(self):
        if self._rag_service is None and self._config.rag_enabled:
            from src.infrastructure.rag.rag_service import RAGService

            self._rag_service = RAGService()
        return self._rag_service

    async def execute(
        self,
        template_name: str,
        context: dict[str, Any],
        interaction_type: str,
        assessment_id: UUID | None = None,
        store_interaction: bool = True,
    ) -> dict[str, Any]:
        """Execute an AI prompt with RAG context injection and return structured response.

        Args:
            template_name: Name of prompt template
            context: Variables for template rendering
            interaction_type: Type of interaction (bootstrap, review, etc.)
            assessment_id: Optional assessment ID for logging
            store_interaction: Whether to log to database

        Returns:
            Parsed JSON response from LLM
        """
        system_prompt = self._build_system_prompt(interaction_type)
        user_prompt = self._templates.render(template_name, context)

        rag_context = None
        rag = self._get_rag_service()
        if rag:
            try:
                query_text = context.get("rag_query", user_prompt[:500])
                category = context.get("rag_category")
                results = await rag.query(
                    query_text=query_text,
                    n_results=self._config.rag_n_results,
                    category_filter=category,
                )
                if results:
                    rag_context = rag.build_context(results, max_chars=self._config.rag_max_context_chars)
            except Exception as e:
                logger.warning("RAG retrieval failed (continuing without context): %s", e)

        if rag_context:
            system_prompt += (
                "\n\n--- CONTESTO NORMATIVO E TECNICO (da documenti di riferimento) ---\n"
                + rag_context
                + "\n--- FINE CONTESTO ---\n\n"
                "Usa il contesto sopra come riferimento primario. Cita le fonti quando possibile. "
                "Se il contesto non contiene informazioni rilevanti, rispondi basandoti sulla tua conoscenza."
            )

        cache_key = f"{template_name}:{hash(user_prompt)}"
        if self._config.cache_enabled and cache_key in self._cache:
            logger.info("Using cached response for %s", template_name)
            response = self._cache[cache_key]
        else:
            request = LLMRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=750,
                temperature=0.3,
            )
            response = await self._call_with_retries(request)
            if self._config.cache_enabled:
                self._cache[cache_key] = response

        try:
            result = self._parse_json_response(response.content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON, returning raw content: %s", e)
            result = {"raw_content": response.content, "parse_error": str(e)}

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

        raise AIOrchestratorError(f"LLM call failed after {self._config.max_retries} retries: {last_error}")

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
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
                prompt=prompt[:10000],
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
