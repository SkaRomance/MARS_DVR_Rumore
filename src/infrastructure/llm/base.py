"""LLM Provider abstraction layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    """Request for LLM generation."""

    prompt: str
    system_prompt: str | None = None
    max_tokens: int = 500
    temperature: float = 0.7
    stop: list[str] | None = None


@dataclass
class LLMResponse:
    """Response from LLM generation."""

    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Concrete implementations:
    - OllamaProvider: For Ollama local/cloud
    - OpenAIProvider: For OpenAI API
    - MockProvider: For testing without real API
    """

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate completion from LLM.

        Args:
            request: LLMRequest with prompt and settings

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: If generation fails
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available and responding.

        Returns:
            True if provider can accept requests
        """
        pass

    async def generate_structured(
        self, request: LLMRequest, response_format: dict[str, Any] | None = None
    ) -> LLMResponse:
        """Generate with structured output request.

        Default implementation ignores structured format.
        Override for providers that support it natively.
        """
        return await self.generate(request)


class LLMProviderError(Exception):
    """Error raised by LLM provider."""

    pass


class LLMProviderUnavailableError(LLMProviderError):
    """Provider is not available."""

    pass


class LLMProviderTimeoutError(LLMProviderError):
    """Provider request timed out."""

    pass
