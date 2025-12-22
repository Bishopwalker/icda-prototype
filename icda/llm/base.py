"""
Base LLM Client Interface.

Defines the abstract interface for all secondary LLM providers.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMConfig:
    """Provider-agnostic LLM configuration."""

    # Provider identification
    provider: str = "auto"  # auto, gemini, openai, claude, openrouter
    api_key: Optional[str] = None
    model: Optional[str] = None  # Provider-specific model name

    # Generation parameters
    temperature: float = 0.3  # Low for consistency in enforcement
    max_tokens: int = 2048
    timeout: int = 60

    # Optional endpoint override (for self-hosted or proxies)
    base_url: Optional[str] = None

    def __post_init__(self):
        """Set default model based on provider if not specified."""
        if self.model is None:
            self.model = self._default_model()

    def _default_model(self) -> str:
        """Get default model for the provider."""
        defaults = {
            "gemini": "gemini-2.0-flash",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-5-haiku-latest",
            "openrouter": "anthropic/claude-3.5-haiku",
        }
        return defaults.get(self.provider, "default")


@dataclass(slots=True)
class LLMResponse:
    """Standardized response from any LLM provider."""
    success: bool
    text: str = ""
    error: Optional[str] = None
    usage: dict = field(default_factory=dict)
    provider: str = "unknown"
    model: str = "unknown"
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "text": self.text,
            "error": self.error,
            "usage": self.usage,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
        }


class BaseLLMClient(ABC):
    """
    Abstract base class for secondary LLM providers.

    All enforcement components (ChunkGate, QueryReviewer, etc.) depend
    only on this interface, making them provider-agnostic.

    Implementations:
    - GeminiClient: Google Gemini (gemini-2.0-flash)
    - OpenAIClient: OpenAI GPT (gpt-4o-mini)
    - ClaudeClient: Anthropic Claude (claude-3.5-haiku)
    - OpenRouterClient: OpenRouter (any model)
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.available = False
        self._provider_name = "base"

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return self._provider_name

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt / main content
            system_prompt: Optional system instruction

        Returns:
            LLMResponse with result or error
        """
        pass

    async def close(self) -> None:
        """Cleanup resources. Override if needed."""
        pass

    def get_info(self) -> dict[str, Any]:
        """Get client info for debugging."""
        return {
            "provider": self._provider_name,
            "available": self.available,
            "model": self.config.model if self.config else None,
        }
