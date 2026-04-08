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
        """Generate completion using Ollama API."""
        messages = []
        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": request.system_prompt,
                }
            )
        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

        if request.stop:
            payload["stop"] = request.stop

        try:
            response = await self._client.post(
                "/chat/completions",
                json=payload,
            )

            if response.status_code == 401:
                raise LLMProviderError("Invalid API key for Ollama")
            elif response.status_code == 404:
                raise LLMProviderError(f"Model '{self.model}' not found")
            elif response.status_code != 200:
                raise LLMProviderError(
                    f"Ollama API error: {response.status_code} - {response.text}"
                )

            data = response.json()

            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "stop")

            tokens_used = 0
            if "usage" in data:
                tokens_used = data["usage"].get("total_tokens", 0)

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
            response = await self._client.get("/models")
            return response.status_code == 200
        except Exception as e:
            logger.warning("Ollama availability check failed: %s", e)
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        try:
            response = await self._client.get("/models")
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            return []
        except Exception:
            return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
