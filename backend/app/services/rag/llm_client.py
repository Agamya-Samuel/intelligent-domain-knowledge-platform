"""
LLM client — inference interface for vLLM on Modal.com.

Provides an OpenAI-compatible client for communicating with the vLLM
inference endpoint deployed on Modal. Supports both streaming and
non-streaming generation.

In v1, the LLM runs on Modal with vLLM serving (scale-to-zero).
The base URL points to the vLLM OpenAI-compatible endpoint.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """A complete (non-streamed) LLM response."""

    content: str
    model: str
    finish_reason: str
    usage: dict[str, int] = field(default_factory=dict)


def _get_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client pointing at the vLLM endpoint."""
    return AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key="not-needed-for-vllm",  # vLLM doesn't require real API key
        max_retries=2,
        timeout=60.0,
    )


async def generate(
    prompt: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> LLMResponse:
    """
    Generate a complete (non-streaming) response from the LLM.

    Args:
        prompt: The user prompt / assembled RAG prompt.
        max_tokens: Max tokens to generate (defaults to settings.LLM_MAX_TOKENS).
        temperature: Sampling temperature (defaults to settings.LLM_TEMPERATURE).
        model: Model name override.
        system_prompt: Optional system message.

    Returns:
        LLMResponse with generated content and metadata.

    Raises:
        RuntimeError: If the LLM call fails.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=model or settings.LLM_MODEL,
            messages=messages,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            temperature=temperature or settings.LLM_TEMPERATURE,
            stream=False,
        )

        choice = response.choices[0]
        usage_dict = {}
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            finish_reason=choice.finish_reason or "stop",
            usage=usage_dict,
        )

    except Exception as exc:
        logger.exception("LLM generation failed")
        raise RuntimeError(f"LLM generation failed: {exc}") from exc


async def generate_stream(
    prompt: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from the LLM response.

    Yields:
        Individual token strings as they arrive from vLLM.

    Raises:
        RuntimeError: If the LLM call fails.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    client = _get_client()
    try:
        stream = await client.chat.completions.create(
            model=model or settings.LLM_MODEL,
            messages=messages,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            temperature=temperature or settings.LLM_TEMPERATURE,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as exc:
        logger.exception("LLM streaming failed")
        raise RuntimeError(f"LLM streaming failed: {exc}") from exc
