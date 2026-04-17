"""Ollama provider - Supports local + cloud API (OpenAI-compatible chat/completions)."""

import logging
from typing import Any

import httpx

from src.bootstrap.config import get_settings
from src.infrastructure.llm.base import (
    LLMProvider,
    LLMProviderError,
    LLMProviderTimeoutError,
    LLMRequest,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama provider supporting local (/api/generate) and cloud (/v1/chat/completions).

    When api_key is set, automatically uses cloud mode (OpenAI-compatible).
    Without api_key, uses local Ollama (/api/generate).
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        settings = get_settings()

        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.api_key = api_key or settings.ollama_api_key
        self.model = model or settings.ollama_model
        self.timeout = timeout
        self._is_cloud = bool(self.api_key)

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using appropriate Ollama API mode."""
        if self._is_cloud:
            return await self._generate_cloud(request)
        return await self._generate_local(request)

    async def _generate_cloud(self, request: LLMRequest) -> LLMResponse:
        """Generate via Ollama Cloud /v1/chat/completions (OpenAI-compatible)."""
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

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
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )

            if response.status_code == 401:
                raise LLMProviderError("Invalid API key for Ollama Cloud")
            elif response.status_code == 404:
                raise LLMProviderError(f"Model '{self.model}' not found on Ollama Cloud")
            elif response.status_code != 200:
                raise LLMProviderError(f"Ollama Cloud API error: {response.status_code} - {response.text[:500]}")

            data = response.json()

            content = ""
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")

            if not content:
                content = "[No response generated]"

            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            if tokens_used == 0:
                tokens_used = (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)

            finish_reason = choices[0].get("finish_reason", "stop") if choices else "stop"

            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                tokens_used=tokens_used,
                finish_reason=finish_reason,
            )

        except httpx.TimeoutException as e:
            raise LLMProviderTimeoutError(f"Ollama Cloud request timed out: {e}")
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"Ollama Cloud generation failed: {e}")

    async def _generate_local(self, request: LLMRequest) -> LLMResponse:
        """Generate via local Ollama /api/generate."""
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
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

            if response.status_code == 404:
                raise LLMProviderError(f"Model '{self.model}' not found locally")
            elif response.status_code != 200:
                raise LLMProviderError(f"Ollama API error: {response.status_code} - {response.text[:500]}")

            data = response.json()
            content = data.get("response", "")
            if not content:
                content = "[No response generated]"

            tokens_used = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
            finish_reason = data.get("done_reason", "stop")

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
            )

        except httpx.TimeoutException as e:
            raise LLMProviderTimeoutError(f"Ollama request timed out: {e}")
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"Ollama generation failed: {e}")

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via Ollama Cloud /v1/embeddings or local /api/embeddings.

        Returns:
            List of embedding vectors (one per input text).
        """
        payload = {"model": self.model, "input": texts}

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/v1/embeddings" if self._is_cloud else f"{self.base_url}/api/embeddings"

        if not self._is_cloud:
            payload = {
                "model": self.model,
                "prompt": texts[0] if len(texts) == 1 else texts,
            }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

            if response.status_code != 200:
                raise LLMProviderError(f"Embedding API error: {response.status_code} - {response.text[:500]}")

            data = response.json()

            if self._is_cloud:
                return [item["embedding"] for item in data.get("data", [])]
            else:
                embedding = data.get("embedding", [])
                return [embedding] if embedding else []

        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"Embedding generation failed: {e}")

    async def is_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            endpoint = f"{self.base_url}/v1/models" if self._is_cloud else f"{self.base_url}/api/tags"
            response = await self._client.get(endpoint)
            return response.status_code == 200
        except Exception as e:
            logger.warning("Ollama availability check failed: %s", e)
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        try:
            endpoint = f"{self.base_url}/v1/models" if self._is_cloud else f"{self.base_url}/api/tags"
            response = await self._client.get(endpoint)
            if response.status_code == 200:
                data = response.json()
                if self._is_cloud:
                    return data.get("data", [])
                return data.get("models", [])
            return []
        except Exception:
            return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
