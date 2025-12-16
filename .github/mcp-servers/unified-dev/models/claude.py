"""
Anthropic Claude Model Integration
User's primary model with subscription
"""

import os
from typing import List, Dict
from .base import BaseModel


class ClaudeModel(BaseModel):
    """
    Anthropic Claude integration

    Uses Anthropic SDK for Claude API access
    Primary model for user (has subscription)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = None

        if self.api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
            except ImportError:
                # anthropic SDK not installed
                pass

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text completion

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (system, max_tokens, temperature)

        Returns:
            Generated text
        """
        if not self.is_available():
            raise ValueError("Claude model not available - check API key")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)
        system = kwargs.get('system', '')

        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system if system else None,
            messages=messages
        )

        return response.content[0].text

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Chat completion with message history

        Args:
            messages: List of messages [{"role": "user", "content": "..."}, ...]
            **kwargs: Additional parameters

        Returns:
            Assistant response
        """
        if not self.is_available():
            raise ValueError("Claude model not available - check API key")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)
        system = kwargs.get('system', '')

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system if system else None,
            messages=messages
        )

        return response.content[0].text

    def is_available(self) -> bool:
        """
        Check if Claude is available

        Returns:
            True if API key present and client initialized
        """
        return self.api_key is not None and self.client is not None

    def get_name(self) -> str:
        """
        Get model identifier

        Returns:
            Model name
        """
        return f"claude-{self.config.model}"
