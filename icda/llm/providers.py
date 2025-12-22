"""
LLM Provider Implementations.

Contains concrete implementations for various LLM providers:
- Gemini (Google)
- OpenAI (GPT)
- Claude (Anthropic)
- OpenRouter (multi-provider gateway)
"""

import asyncio
import os
import time
import logging
from typing import Any, Optional

from .base import BaseLLMClient, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """
    Google Gemini client.

    Uses google-genai SDK with httpx REST fallback.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._provider_name = "gemini"
        self._use_sdk = False
        self._http_client = None
        self._sdk_client = None

        # Get API key
        api_key = self.config.api_key or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            logger.info("Gemini: No API key - client disabled")
            return

        self.config.api_key = api_key

        # Set default model if not specified
        if not self.config.model or self.config.model == "default":
            self.config.model = "gemini-2.0-flash"

        # Try SDK first
        try:
            from google import genai
            self._sdk_client = genai.Client(api_key=api_key)
            self._use_sdk = True
            self.available = True
            logger.info(f"Gemini: Connected via SDK ({self.config.model})")
        except ImportError:
            # Fallback to REST
            try:
                import httpx
                self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
                self.available = True
                logger.info(f"Gemini: Connected via REST ({self.config.model})")
            except ImportError:
                logger.warning("Gemini: No HTTP client - install httpx")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate using Gemini."""
        if not self.available:
            return LLMResponse(
                success=False,
                error="Gemini not available",
                provider=self._provider_name,
            )

        start = time.time()
        try:
            if self._use_sdk:
                result = await self._generate_sdk(prompt, system_prompt)
            else:
                result = await self._generate_rest(prompt, system_prompt)
            result.latency_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return LLMResponse(
                success=False,
                error=str(e),
                provider=self._provider_name,
                latency_ms=int((time.time() - start) * 1000),
            )

    async def _generate_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using google-genai SDK."""
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        loop = asyncio.get_event_loop()

        def _generate():
            return self._sdk_client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=config,
            )

        response = await loop.run_in_executor(None, _generate)

        return LLMResponse(
            success=True,
            text=response.text if hasattr(response, "text") else str(response),
            usage={
                "prompt_tokens": getattr(response, "prompt_token_count", 0),
                "completion_tokens": getattr(response, "candidates_token_count", 0),
            },
            provider=self._provider_name,
            model=self.config.model,
        )

    async def _generate_rest(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"

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

        text = ""
        try:
            candidates = result.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
        except (KeyError, IndexError):
            pass

        return LLMResponse(
            success=True,
            text=text,
            usage=result.get("usageMetadata", {}),
            provider=self._provider_name,
            model=self.config.model,
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()


class OpenAIClient(BaseLLMClient):
    """
    OpenAI GPT client.

    Uses openai SDK or httpx REST fallback.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._provider_name = "openai"
        self._client = None
        self._http_client = None

        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")

        if not api_key:
            logger.info("OpenAI: No API key - client disabled")
            return

        self.config.api_key = api_key

        if not self.config.model or self.config.model == "default":
            self.config.model = "gpt-4o-mini"

        # Try SDK first
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            self.available = True
            logger.info(f"OpenAI: Connected via SDK ({self.config.model})")
        except ImportError:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
                self.available = True
                logger.info(f"OpenAI: Connected via REST ({self.config.model})")
            except ImportError:
                logger.warning("OpenAI: No HTTP client - install httpx or openai")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate using OpenAI."""
        if not self.available:
            return LLMResponse(
                success=False,
                error="OpenAI not available",
                provider=self._provider_name,
            )

        start = time.time()
        try:
            if self._client:
                result = await self._generate_sdk(prompt, system_prompt)
            else:
                result = await self._generate_rest(prompt, system_prompt)
            result.latency_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return LLMResponse(
                success=False,
                error=str(e),
                provider=self._provider_name,
                latency_ms=int((time.time() - start) * 1000),
            )

    async def _generate_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using openai SDK."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return LLMResponse(
            success=True,
            text=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            provider=self._provider_name,
            model=self.config.model,
        )

    async def _generate_rest(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using REST API."""
        url = self.config.base_url or "https://api.openai.com/v1/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return LLMResponse(
            success=True,
            text=text,
            usage=result.get("usage", {}),
            provider=self._provider_name,
            model=self.config.model,
        )

    async def close(self) -> None:
        """Close clients."""
        if self._http_client:
            await self._http_client.aclose()
        if self._client:
            await self._client.close()


class ClaudeClient(BaseLLMClient):
    """
    Anthropic Claude client.

    Uses anthropic SDK or httpx REST fallback.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._provider_name = "claude"
        self._client = None
        self._http_client = None

        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            logger.info("Claude: No API key - client disabled")
            return

        self.config.api_key = api_key

        if not self.config.model or self.config.model == "default":
            self.config.model = "claude-3-5-haiku-latest"

        # Try SDK first
        try:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            self.available = True
            logger.info(f"Claude: Connected via SDK ({self.config.model})")
        except ImportError:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
                self.available = True
                logger.info(f"Claude: Connected via REST ({self.config.model})")
            except ImportError:
                logger.warning("Claude: No HTTP client - install httpx or anthropic")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate using Claude."""
        if not self.available:
            return LLMResponse(
                success=False,
                error="Claude not available",
                provider=self._provider_name,
            )

        start = time.time()
        try:
            if self._client:
                result = await self._generate_sdk(prompt, system_prompt)
            else:
                result = await self._generate_rest(prompt, system_prompt)
            result.latency_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            return LLMResponse(
                success=False,
                error=str(e),
                provider=self._provider_name,
                latency_ms=int((time.time() - start) * 1000),
            )

    async def _generate_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using anthropic SDK."""
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._client.messages.create(**kwargs)

        text = ""
        if response.content:
            text = response.content[0].text

        return LLMResponse(
            success=True,
            text=text,
            usage={
                "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                "completion_tokens": response.usage.output_tokens if response.usage else 0,
            },
            provider=self._provider_name,
            model=self.config.model,
        )

    async def _generate_rest(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        """Generate using REST API."""
        url = self.config.base_url or "https://api.anthropic.com/v1/messages"

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }

        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        text = ""
        if result.get("content"):
            text = result["content"][0].get("text", "")

        return LLMResponse(
            success=True,
            text=text,
            usage=result.get("usage", {}),
            provider=self._provider_name,
            model=self.config.model,
        )

    async def close(self) -> None:
        """Close clients."""
        if self._http_client:
            await self._http_client.aclose()
        if self._client:
            await self._client.close()


class OpenRouterClient(BaseLLMClient):
    """
    OpenRouter client - multi-provider gateway.

    Supports any model available on OpenRouter (GPT, Claude, Gemini, Mistral, etc.)
    Uses OpenAI-compatible API format.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._provider_name = "openrouter"
        self._http_client = None

        api_key = self.config.api_key or os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            logger.info("OpenRouter: No API key - client disabled")
            return

        self.config.api_key = api_key

        if not self.config.model or self.config.model == "default":
            self.config.model = "anthropic/claude-3.5-haiku"

        try:
            import httpx
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
            self.available = True
            logger.info(f"OpenRouter: Connected ({self.config.model})")
        except ImportError:
            logger.warning("OpenRouter: No HTTP client - install httpx")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate using OpenRouter."""
        if not self.available:
            return LLMResponse(
                success=False,
                error="OpenRouter not available",
                provider=self._provider_name,
            )

        start = time.time()
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "HTTP-Referer": "https://icda-prototype.local",
                "X-Title": "ICDA Prototype",
            }

            response = await self._http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()

            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            return LLMResponse(
                success=True,
                text=text,
                usage=result.get("usage", {}),
                provider=self._provider_name,
                model=self.config.model,
                latency_ms=int((time.time() - start) * 1000),
            )

        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            return LLMResponse(
                success=False,
                error=str(e),
                provider=self._provider_name,
                latency_ms=int((time.time() - start) * 1000),
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()


class DisabledClient(BaseLLMClient):
    """
    Disabled/fallback client.

    Used when no provider is available. Always returns success
    with default values to allow graceful degradation.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config)
        self._provider_name = "disabled"
        self.available = False
        logger.info("LLM: No provider available - enforcement disabled")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Return disabled response."""
        return LLMResponse(
            success=False,
            error="No LLM provider configured",
            provider=self._provider_name,
        )
