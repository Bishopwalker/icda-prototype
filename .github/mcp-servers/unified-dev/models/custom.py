"""
Custom Model Integration
Supports OpenRouter, local models, or any custom API provider
"""

import os
from typing import List, Dict
from .base import BaseModel
import httpx


class CustomModel(BaseModel):
    """
    Custom model provider integration

    Supports:
    - OpenRouter (https://openrouter.ai)
    - Local models (Ollama, LocalAI, etc.)
    - Any OpenAI-compatible API

    Configuration via config.json:
    {
        "provider": "openrouter",
        "model": "anthropic/claude-3.5-sonnet",
        "api_url": "https://openrouter.ai/api/v1",
        ...
    }
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.provider = config.get('provider', 'custom')
        self.api_url = config.get('api_url', '')
        self.api_key = os.getenv('CUSTOM_MODEL_API_KEY')

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text completion via custom API

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        if not self.is_available():
            raise ValueError(f"Custom model ({self.provider}) not available - check configuration")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)
        system = kwargs.get('system', 'You are a helpful coding assistant.')

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]

        return await self._make_request(messages, max_tokens, temperature)

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
            raise ValueError(f"Custom model ({self.provider}) not available - check configuration")

        max_tokens = kwargs.get('max_tokens', self.config.max_tokens)
        temperature = kwargs.get('temperature', self.config.temperature)

        return await self._make_request(messages, max_tokens, temperature)

    async def _make_request(self, messages: List[Dict], max_tokens: int, temperature: float) -> str:
        """
        Make HTTP request to custom API endpoint

        Args:
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Model response text
        """
        headers = {
            'Content-Type': 'application/json'
        }

        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        # OpenRouter specific headers
        if self.provider == 'openrouter':
            headers['HTTP-Referer'] = 'https://github.com/yourusername/ebl'
            headers['X-Title'] = 'EBL Unified MCP Server'

        payload = {
            'model': self.config.model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload
            )

            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            elif 'response' in data:
                return data['response']
            else:
                raise ValueError(f"Unexpected response format from {self.provider}")

    def is_available(self) -> bool:
        """
        Check if custom model is available

        Returns:
            True if API URL is configured

        Note:
            API key may be optional for local models
        """
        return bool(self.api_url)

    def get_name(self) -> str:
        """
        Get model identifier

        Returns:
            Model name with provider
        """
        return f"{self.provider}-{self.config.model}"
