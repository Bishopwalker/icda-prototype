"""
Base Model Interface
Abstract base class that all model integrations must implement
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for a model"""
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    description: str = ""


class BaseModel(ABC):
    """
    Abstract base class for all model integrations

    All model implementations (Claude, Codex, Custom) must implement these methods
    """

    def __init__(self, config: dict):
        """
        Initialize model with configuration

        Args:
            config: Model configuration from config.json
        """
        self.config = ModelConfig(**config)

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text completion

        Args:
            prompt: Input prompt
            **kwargs: Additional model-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: If generation fails
        """
        pass

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Chat completion with message history

        Args:
            messages: List of messages [{"role": "user", "content": "..."}, ...]
            **kwargs: Additional model-specific parameters

        Returns:
            Assistant response

        Raises:
            Exception: If chat fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if model is currently available

        Returns:
            True if model can be used, False otherwise

        Note:
            - Check API key presence
            - Check credits (for pay-per-use models)
            - Check connectivity (for remote models)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get model identifier

        Returns:
            Model name/identifier
        """
        pass

    async def embed(self, text: str) -> List[float]:
        """
        Generate embeddings (optional, not all models support this)

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            NotImplementedError: If model doesn't support embeddings
        """
        raise NotImplementedError(f"{self.get_name()} does not support embeddings")
