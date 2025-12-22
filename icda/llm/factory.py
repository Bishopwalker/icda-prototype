"""
LLM Provider Factory.

Auto-detects available providers from environment variables
and creates the appropriate client.
"""

import os
import logging
from typing import Optional

from .base import BaseLLMClient, LLMConfig
from .providers import (
    GeminiClient,
    OpenAIClient,
    ClaudeClient,
    OpenRouterClient,
    DisabledClient,
)

logger = logging.getLogger(__name__)

# Provider priority order (first available wins)
PROVIDER_PRIORITY = ["gemini", "openai", "claude", "openrouter"]

# Environment variable mapping
PROVIDER_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# Client class mapping
PROVIDER_CLIENTS = {
    "gemini": GeminiClient,
    "openai": OpenAIClient,
    "claude": ClaudeClient,
    "openrouter": OpenRouterClient,
}


def get_available_providers() -> list[str]:
    """
    Get list of available providers based on environment variables.

    Returns:
        List of provider names with valid API keys
    """
    available = []
    for provider, env_key in PROVIDER_ENV_KEYS.items():
        if os.environ.get(env_key):
            available.append(provider)
    return available


def create_llm_client(
    provider: str = "auto",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """
    Create an LLM client with auto-detection or explicit provider.

    Args:
        provider: Provider name or "auto" for auto-detection
        api_key: Optional explicit API key
        model: Optional model override
        **kwargs: Additional config options

    Returns:
        Configured BaseLLMClient instance

    Example:
        # Auto-detect (uses first available)
        client = create_llm_client()

        # Explicit provider
        client = create_llm_client("claude", model="claude-3-5-sonnet")

        # With API key
        client = create_llm_client("openai", api_key="sk-...")
    """
    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        **kwargs,
    )

    if provider == "auto":
        return _create_auto_client(config)

    # Explicit provider
    if provider in PROVIDER_CLIENTS:
        client = PROVIDER_CLIENTS[provider](config)
        if client.available:
            return client
        logger.warning(f"LLM: {provider} requested but not available")

    # Fallback to disabled
    return DisabledClient(config)


def _create_auto_client(config: LLMConfig) -> BaseLLMClient:
    """
    Auto-detect and create the best available client.

    Tries providers in priority order:
    1. Gemini (fast, cost-effective)
    2. OpenAI (widely available)
    3. Claude (high quality)
    4. OpenRouter (fallback gateway)
    """
    available = get_available_providers()

    if not available:
        logger.info("LLM: No provider API keys found - enforcement disabled")
        return DisabledClient(config)

    # Log available providers
    logger.info(f"LLM: Available providers: {', '.join(available)}")

    # Try in priority order
    for provider in PROVIDER_PRIORITY:
        if provider in available:
            # Create config for this specific provider
            provider_config = LLMConfig(
                provider=provider,
                api_key=config.api_key,
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                base_url=config.base_url,
            )

            client = PROVIDER_CLIENTS[provider](provider_config)
            if client.available:
                logger.info(f"LLM: Using {provider} ({client.config.model})")
                return client

    # No provider worked
    return DisabledClient(config)


def create_llm_client_from_config(
    provider: str = "auto",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    timeout: int = 60,
    enabled: bool = True,
) -> BaseLLMClient:
    """
    Create LLM client from explicit config values.

    This is the integration point for icda.config.Config.

    Args:
        provider: Provider name or "auto"
        api_key: API key (if empty, reads from env)
        model: Model name (if empty, uses provider default)
        temperature: Generation temperature
        max_tokens: Max tokens
        timeout: Request timeout
        enabled: Feature flag

    Returns:
        Configured LLM client
    """
    if not enabled:
        logger.info("LLM: Enforcer disabled by config")
        return DisabledClient()

    return create_llm_client(
        provider=provider,
        api_key=api_key if api_key else None,
        model=model if model else None,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
