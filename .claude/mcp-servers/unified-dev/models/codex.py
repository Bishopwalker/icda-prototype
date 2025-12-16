"""
OpenAI Codex/GPT-4 Model Integration
Used when user has credits available
"""

import os
from typing import List, Dict
from .base import BaseModel


class CodexModel(BaseModel):
    """
    OpenAI GPT-4/Codex integration

    Fallback model when user has OpenAI credits
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.check_credits = config.get('check_credits', True)
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                # openai SDK not installed
                pass

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text completion

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        if not self.is_available():
            raise ValueError("Codex model not available - check API key or credits")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)
        system = kwargs.get('system', 'You are a helpful coding assistant.')

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]

        response = self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages
        )

        return response.choices[0].message.content

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
            raise ValueError("Codex model not available - check API key or credits")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)

        response = self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages
        )

        return response.choices[0].message.content

    def is_available(self) -> bool:
        """
        Check if Codex is available

        Returns:
            True if API key present, client initialized, and (optionally) credits available

        Note:
            Credit checking not implemented yet - assumes available if API key present
            Could be enhanced to check account balance via API
        """
        if not self.api_key or not self.client:
            return False

        # TODO: Implement credit checking if check_credits is True
        # For now, assume available if API key is present
        return True

    def get_name(self) -> str:
        """
        Get model identifier

        Returns:
            Model name
        """
        return f"openai-{self.config.model}"
