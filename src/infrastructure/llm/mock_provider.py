"""Mock LLM provider for testing without real API calls."""

import json
from src.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse


class MockProvider(LLMProvider):
    """Mock LLM provider that returns predefined responses.

    Useful for testing without network calls or API keys.
    """

    def __init__(
        self,
        response_content: str = '{"result": "mocked response"}',
        model: str = "mock-model",
    ):
        self.response_content = response_content
        self.model = model
        self._call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Return mock response."""
        self._call_count += 1

        return LLMResponse(
            content=self.response_content,
            model=self.model,
            tokens_used=len(request.prompt.split()),
            finish_reason="stop",
        )

    async def is_available(self) -> bool:
        """Always available."""
        return True

    @property
    def call_count(self) -> int:
        """Number of times generate was called."""
        return self._call_count

    def configure_response(self, response_content: str):
        """Update the response content for next call."""
        self.response_content = response_content


class MockStreamingProvider(MockProvider):
    """Mock provider that supports streaming responses."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Return mock response."""
        self._call_count += 1

        # Simulate streaming by returning word by word
        words = self.response_content.split()
        streamed_content = ""
        for word in words:
            streamed_content += word + " "

        return LLMResponse(
            content=streamed_content.strip(),
            model=self.model,
            tokens_used=len(request.prompt.split()),
            finish_reason="stop",
        )
