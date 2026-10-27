"""LLM access layer (Groq) with retries, fallback and typed outputs.

All agents call the model through `structured_call`, which:
  1. asks the model for a Pydantic-typed answer (tool calling under the hood),
  2. retries transient errors / HTTP 429 rate limits with backoff (Groq client
     honours the Retry-After header),
  3. falls back from the main model to the fast model if the main one keeps failing,
  4. raises `LLMUnavailableError` so callers can degrade gracefully instead of crashing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from assistant.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailableError(RuntimeError):
    """Raised when every configured model failed (no key, outage, rate limit exhausted)."""


@lru_cache(maxsize=4)
def _chat_model(model_name: str) -> ChatGroq:
    """Create (and cache) one ChatGroq client per model name."""
    if not settings.groq_api_key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add a free key from console.groq.com."
        )
    return ChatGroq(
        model=model_name,
        api_key=settings.groq_api_key,
        temperature=0,  # deterministic-ish output: we want grounded answers, not creativity
        max_retries=settings.llm_max_retries,  # exponential backoff, respects Retry-After on 429
        timeout=settings.llm_timeout_s,
    )


def structured_call(
    schema: type[T],
    system_prompt: str,
    user_prompt: str,
    *,
    tier: str = "main",
    run_name: str | None = None,
) -> T:
    """Call the LLM and parse its reply into `schema`.

    Args:
        schema: Pydantic model describing the expected output.
        system_prompt: role + rules for the agent.
        user_prompt: the task input (question, evidence, ...).
        tier: "main" (strong model, fast model as fallback) or "fast" (fast model only,
            then main as fallback). Lets cheap agents save the main model's token budget.
        run_name: label shown in LangSmith for this LLM call.
    """
    order = (
        [settings.main_model, settings.fast_model]
        if tier == "main"
        else [settings.fast_model, settings.main_model]
    )
    # Raises LLMUnavailableError right away when no API key is configured.
    primary, *fallbacks = [_chat_model(m).with_structured_output(schema) for m in order]
    runnable = primary.with_fallbacks(fallbacks) if fallbacks else primary

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    try:
        result = runnable.invoke(messages, config={"run_name": run_name or schema.__name__})
    except Exception as exc:  # provider down, quota exhausted, malformed tool call on all models
        raise LLMUnavailableError(f"All models failed: {type(exc).__name__}: {exc}") from exc

    if result is None:  # model replied without calling the output tool
        raise LLMUnavailableError("Model returned no structured output.")
    return result


def llm_available() -> bool:
    """Cheap check used by the UI to show a setup hint when no key is configured."""
    return bool(settings.groq_api_key)


__all__ = ["LLMUnavailableError", "structured_call", "llm_available"]
