"""LLM config with Claude Sonnet 4.6 default and OpenAI fallback.

Switch providers via env:
    SHOWCASE_LLM=anthropic (default) | openai
    SHOWCASE_MODEL=<litellm-compatible model string>
"""

from __future__ import annotations

import os

from crewai import LLM


def default_model() -> str:
    """Return the model string for the current provider."""
    override = os.getenv("SHOWCASE_MODEL")
    if override:
        return override

    provider = os.getenv("SHOWCASE_LLM", "anthropic").lower()
    if provider == "openai":
        return "openai/gpt-4.1-mini"
    return "anthropic/claude-sonnet-4-6"


def get_llm(temperature: float = 0.2, **kwargs) -> LLM:
    """Build the showcase LLM. Respects SHOWCASE_LLM / SHOWCASE_MODEL env vars."""
    return LLM(model=default_model(), temperature=temperature, **kwargs)
