"""Ollama provider - Supports Ollama local and cloud API (OpenAI-compatible)."""

import httpx
import logging
from typing import Any

from src.infrastructure.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMProviderError,
    LLMProviderUnavailableError,
    LLMProviderTimeoutError,
)
from src.bootstrap.config import get_settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama provider supporting both local and cloud endpoints.

    Supports OpenAI-compatible API format for Ollama Cloud.

    Usage:
        # Local Ollama
        provider = OllamaProvider()

        # Ollama Cloud
        provider = OllamaProvider(
            base_url="https://api.ollama.com/v1",
            api_key="your-api-key",
            model="glm-5.1"
        )
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        settings = get_settings()

        self.base_url = base_url or settings.ollama_base_url
        self.api_key = api_key or settings.ollama_api_key
        self.model = model or settings.ollama_model
        self.timeout = timeout

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Ollama API.

        Supports both local Ollama (http://localhost:11434) and
        Ollama Cloud (https://ollama.com/api) endpoints.
        """
        # Build combined prompt for /api/generate endpoint
        prompt_text = request.prompt
        if request.system_prompt:
            prompt_text = f"{request.system_prompt}\n\n{request.prompt}"

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt_text,
            "stream": False,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
        }

        if request.stop:
            payload["stop"] = request.stop

        try:
            # Use direct httpx post instead of AsyncClient to avoid redirect issues
            # with base_url for Ollama Cloud
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    headers=headers,
                )

            if response.status_code == 401:
                raise LLMProviderError("Invalid API key for Ollama")
            elif response.status_code == 404:
                raise LLMProviderError(f"Model '{self.model}' not found")
            elif response.status_code == 301:
                raise LLMProviderError(
                    "Ollama Cloud requires direct endpoint, redirect not allowed"
                )
            elif response.status_code != 200:
                raise LLMProviderError(
                    f"Ollama API error: {response.status_code} - {response.text}"
                )

            data = response.json()

            # Parse /api/generate response format
            # GLM models use "thinking" field for reasoning, "response" for final answer
            content = data.get("response", "")
            if not content and "thinking" in data:
                # Model used thinking - extract final answer from end of thinking
                thinking = data.get("thinking", "")
                if isinstance(thinking, str) and len(thinking) > 10:
                    # GLM thinking ends with final check/conclusion
                    # The last line before truncation often contains the answer
                    lines = thinking.strip().split("\n")
                    if lines:
                        # Look for conclusion lines (no leading number/bullet)
                        for line in reversed(lines):
                            stripped = line.strip()
                            if (
                                stripped
                                and not stripped.startswith("*")
                                and not stripped.startswith("**")
                            ):
                                content = stripped
                                break
            if not content:
                content = "[No response generated]"

            finish_reason = data.get("done_reason", "stop")

            # Extract tokens used
            tokens_used = 0
            if "eval_count" in data:
                tokens_used = data["eval_count"]
            if "prompt_eval_count" in data:
                tokens_used += data["prompt_eval_count"]

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
            )

        except httpx.TimeoutException as e:
            raise LLMProviderTimeoutError(f"Ollama request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise LLMProviderUnavailableError(f"Ollama HTTP error: {e}")
        except Exception as e:
            raise LLMProviderError(f"Ollama generation failed: {e}")

    async def is_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            # Use /api/tags endpoint for availability check
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning("Ollama availability check failed: %s", e)
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        try:
            response = await self._client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
            return []
        except Exception:
            return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
