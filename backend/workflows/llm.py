"""Thin Groq helper for structured / streaming LLM calls."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional

from groq import Groq

from .config import WORKFLOW_LLM_MODEL


def get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing from the environment."
        )

    return Groq(api_key=api_key)


def strip_code_fences(text: str) -> str:
    text = text.strip()

    without_fences = re.sub(
        r"^```(?:json|python)?\s*",
        "",
        text,
    )
    without_fences = re.sub(
        r"\s*```$",
        "",
        without_fences,
    )

    return without_fences.strip()


def chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_completion_tokens: int = 4096,
    json_mode: bool = False,
    model: Optional[str] = None,
) -> str:
    client = get_client()

    kwargs: Dict[str, Any] = {
        "model": model or WORKFLOW_LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    completion = client.chat.completions.create(**kwargs)

    return completion.choices[0].message.content or ""


def chat_text(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_completion_tokens: int = 2048,
    model: Optional[str] = None,
) -> str:
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        model=model,
    )


def chat_json(
    system: str,
    user: str,
    temperature: float = 0.1,
    max_completion_tokens: int = 4096,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a parsed JSON dict from the LLM (raises on invalid JSON)."""

    response = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        json_mode=True,
        model=model,
    )

    return json.loads(strip_code_fences(response))


def chat_json_with_retry(
    system: str,
    user: str,
    repair_hints: List[str],
    *,
    attempts: int = 3,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ask for JSON and retry with error feedback when parsing fails.

    Parameters
    ----------
    system : str
        System prompt describing the expected JSON schema.
    user : str
        Initial user request.
    repair_hints : List[str]
        When exhausted, the last hint is re-used for every retry.
    attempts : int
        Maximum number of LLM calls (including the first).
    model : Optional[str]
        Overrides WORKFLOW_LLM_MODEL for this call.
    """

    last_error = ""

    for attempt in range(attempts):
        error_suffix = ""

        if attempt > 0:
            hint = repair_hints[min(attempt - 1, len(repair_hints) - 1)]
            error_suffix = (
                "\n\nYour previous response failed validation "
                f"with this error:\n{last_error}\n\n"
                f"Guidance: {hint}"
            )

        try:
            return chat_json(
                system,
                user + error_suffix,
                model=model,
            )

        except Exception as exc:
            last_error = str(exc)

            if attempt == attempts - 1:
                raise

    raise RuntimeError("Unreachable chat_json retry state.")


def stream_text(
    answer: str,
    chunk_size: int = 64,
) -> Iterator[str]:
    """
    Deterministically split a pre-built answer into token-like chunks.

    The workflow computes the full canonical result first, so we stream
    the rendered markdown in slices rather than streaming raw LLM tokens.
    """

    words = answer.split(" ")
    buffer = ""

    for word in words:
        buffer += word + " "

        if len(buffer) >= chunk_size:
            yield buffer
            buffer = ""

    if buffer:
        yield buffer
