"""
Google Gemini Client.

Provides async client for Gemini API with SDK and REST fallback.
Used by the enforcer pipeline for quality validation.
"""

import asyncio
import os
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiConfig:
    """Configuration for Gemini client."""
    api_key: Optional[str] = None
    model: str = "gemini-2.0-flash"  # Fast, cost-effective for enforcement
    temperature: float = 0.3         # Low temp for consistency
    max_tokens: int = 2048
    timeout: int = 60


class GeminiClient:
    """
    Gemini API client for quality enforcement.

    Gracefully handles missing API key (disabled mode).
    Uses google-genai SDK or falls back to REST API via httpx.

    Usage:
        client = GeminiClient()
        result = await client.generate("Review this text...")
    """

    __slots__ = ("config", "client", "available", "_use_sdk", "_http_client")

    def __init__(self, config: Optional[GeminiConfig] = None):
        self.config = config or GeminiConfig()
        self.client = None
        self.available = False
        self._use_sdk = False
        self._http_client = None

        # Get API key from config or environment
        api_key = self.config.api_key or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            logger.info("Gemini: No API key - enforcement disabled")
            return

        self.config.api_key = api_key

        # Try google-genai SDK first
        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
            self._use_sdk = True
            self.available = True
            logger.info(f"Gemini: Connected via SDK ({self.config.model})")
        except ImportError:
            # Fallback to REST API via httpx
            try:
                import httpx
                self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
                self.available = True
                logger.info(f"Gemini: Connected via REST ({self.config.model})")
            except ImportError:
                logger.warning("Gemini: No HTTP client available - install httpx")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate content with Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction

        Returns:
            Dict with 'success', 'text', 'usage', and 'error' fields
        """
        if not self.available:
            return {"success": False, "error": "Gemini not available", "text": ""}

        try:
            if self._use_sdk:
                return await self._generate_sdk(prompt, system_prompt)
            else:
                return await self._generate_rest(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return {"success": False, "error": str(e), "text": ""}

    async def _generate_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> dict[str, Any]:
        """Generate using google-genai SDK."""
        from google.genai import types

        # Build config
        config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        # Run in executor since SDK may be sync
        loop = asyncio.get_event_loop()

        def _generate():
            return self.client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=config,
            )

        response = await loop.run_in_executor(None, _generate)

        return {
            "success": True,
            "text": response.text if hasattr(response, "text") else str(response),
            "usage": {
                "prompt_tokens": getattr(response, "prompt_token_count", 0),
                "completion_tokens": getattr(response, "candidates_token_count", 0),
            },
        }

    async def _generate_rest(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> dict[str, Any]:
        """Generate using REST API (fallback)."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"

        # Build request
        contents = []

        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System: {system_prompt}"}],
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.config.api_key,
        }

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()

        # Extract text from response
        text = ""
        try:
            candidates = result.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
        except (KeyError, IndexError) as e:
            logger.warning(f"Failed to parse Gemini response: {e}")

        return {
            "success": True,
            "text": text,
            "usage": result.get("usageMetadata", {}),
        }

    async def close(self) -> None:
        """Close HTTP client if using REST mode."""
        if self._http_client:
            await self._http_client.aclose()

    def __del__(self):
        """Cleanup on deletion."""
        if self._http_client and hasattr(self._http_client, "is_closed"):
            if not self._http_client.is_closed:
                # Can't await in __del__, schedule cleanup
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self._http_client.aclose())
                except Exception:
                    pass
