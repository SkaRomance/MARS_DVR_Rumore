"""Tests for Ollama provider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.infrastructure.llm.ollama_provider import OllamaProvider
from src.infrastructure.llm.base import LLMRequest, LLMProviderError


class TestOllamaProvider:
    """Test cases for Ollama provider."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.ollama_base_url = "https://api.ollama.com/v1"
        settings.ollama_api_key = "test-key"
        settings.ollama_model = "glm-5.1"
        return settings

    @pytest.fixture
    def provider(self, mock_settings):
        """Create provider with mocked settings."""
        with patch(
            "src.infrastructure.llm.ollama_provider.get_settings",
            return_value=mock_settings,
        ):
            return OllamaProvider()

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 50},
        }

        with patch.object(provider._client, "post", return_value=mock_response):
            request = LLMRequest(prompt="Test prompt")
            response = await provider.generate(request)

            assert response.content == "Test response"
            assert response.model == "glm-5.1"
            assert response.tokens_used == 50

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self, provider):
        """Test generation with system prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 30},
        }

        with patch.object(
            provider._client, "post", return_value=mock_response
        ) as mock_post:
            request = LLMRequest(
                prompt="User prompt",
                system_prompt="System prompt",
            )
            await provider.generate(request)

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert len(payload["messages"]) == 2
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_is_available_success(self, provider):
        """Test availability check success."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(provider._client, "get", return_value=mock_response):
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_failure(self, provider):
        """Test availability check failure."""
        with patch.object(
            provider._client, "get", side_effect=Exception("Network error")
        ):
            assert await provider.is_available() is False
