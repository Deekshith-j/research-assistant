"""LLM access layer (Groq) with retries, fallback and typed outputs.

All agents call the model through `structured_call`, which:
  1. asks the model for a Pydantic-typed answer (tool calling under the hood),
  2. if that model returns malformed structured output, retries the SAME model in
     JSON mode with the schema in the prompt (some models fail tool calling on nested
     schemas, e.g. Qwen on the Analyst's output - an acceptance-test finding),
  3. retries transient errors / HTTP 429 rate limits with backoff (Groq client
     honours the Retry-After header),
  4. falls back from the main model to the fast model, then to any
     GROQ_FALLBACK_MODELS (each model has its own daily quota),
  5. raises `LLMUnavailableError` listing every model's failure, so callers can
     degrade gracefully and the reason is visible in the trace.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TypeVar

from groq import BadRequestError
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, ValidationError

from assistant.config import settings

T = TypeVar("T", bound=BaseModel)

# Errors that mean "this model produced unusable structured output" (worth a JSON-mode
# retry on the same model), as opposed to rate limits / outages (move to the next model).
_MALFORMED = (BadRequestError, OutputParserException, ValidationError)


class LLMUnavailableError(RuntimeError):
    """Raised when every configured model failed (no key, outage, rate limit exhausted)."""


@lru_cache(maxsize=8)
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


def _model_order(tier: str) -> list[str]:
    """Models to try, in order, for an agent of the given tier."""
    order = [settings.main_model, settings.fast_model] if tier == "main" else [settings.fast_model, settings.main_model]
    return order + [m for m in settings.fallback_models if m not in order]


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
        tier: "main" (strong model first) or "fast" (fast model first). Lets cheap
            agents save the main model's token budget.
        run_name: label shown in LangSmith for this LLM call.
    """
    name = run_name or schema.__name__
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    # Same instructions plus the exact JSON schema, for the JSON-mode retry.
    json_messages = [
        SystemMessage(content=f"{system_prompt}\n\nRespond ONLY with one JSON object that matches this "
                              f"JSON schema:\n{json.dumps(schema.model_json_schema())}"),
        HumanMessage(content=user_prompt),
    ]

    failures: list[str] = []
    for model_name in _model_order(tier):
        llm = _chat_model(model_name)  # raises LLMUnavailableError when no API key is configured
        attempts = [
            ("tools", llm.with_structured_output(schema), messages),
            ("json", llm.with_structured_output(schema, method="json_mode"), json_messages),
        ]
        for mode, runnable, msgs in attempts:
            try:
                result = runnable.invoke(msgs, config={"run_name": f"{name} [{model_name}, {mode}]"})
            except _MALFORMED as exc:
                failures.append(f"{model_name}/{mode}: malformed output ({type(exc).__name__})")
                continue  # same model, JSON mode
            except Exception as exc:  # rate limit, outage, timeout -> next model
                failures.append(f"{model_name}/{mode}: {type(exc).__name__}: {str(exc)[:160]}")
                break
            if result is not None:
                return result
            failures.append(f"{model_name}/{mode}: no structured output")

    raise LLMUnavailableError("All models failed: " + " | ".join(failures))


def llm_available() -> bool:
    """Cheap check used by the UI to show a setup hint when no key is configured."""
    return bool(settings.groq_api_key)


__all__ = ["LLMUnavailableError", "structured_call", "llm_available"]
