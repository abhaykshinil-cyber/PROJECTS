"""
ollama_client.py — Thin wrapper around the Ollama Python library.

Provides a single callable surface, ``ask_llm()``, for all LLM interactions.
All inference runs locally via Ollama at http://localhost:11434 — no API keys
are required or used.

Model: qwen3:8b (configurable via settings.OLLAMA_MODEL)
"""

from typing import Optional

import ollama

from config import settings
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Module setup
# ---------------------------------------------------------------------------

logger = get_logger(__name__)

# System prompt used when none is provided by the caller.
_DEFAULT_SYSTEM = (
    "You are a helpful AI assistant. Be concise and precise in your responses."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ask_llm(
    prompt: str,
    system: Optional[str] = None,
    model: str = settings.OLLAMA_MODEL,
) -> str:
    """
    Send a prompt to the local Ollama instance and return the response text.

    Thinking mode is disabled by prepending ``/no_think`` to the prompt so
    that qwen3:8b returns a direct answer without chain-of-thought output.

    Args:
        prompt: The user-turn message to send.
        system: Optional system prompt that sets the assistant role.
                Defaults to a generic helpful-assistant instruction.
        model:  Ollama model identifier (default: ``settings.OLLAMA_MODEL``).

    Returns:
        Stripped response string on success, or ``""`` on any failure.
        Callers should treat an empty string as a signal to use a heuristic
        fallback.
    """
    system_content = system if system is not None else _DEFAULT_SYSTEM

    # Disable thinking mode for qwen3:8b — prepend the /no_think directive.
    full_prompt = f"/no_think\n{prompt}"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": full_prompt},
    ]

    logger.debug("LLM prompt (truncated): %s", prompt[:200])

    try:
        response = ollama.chat(model=model, messages=messages)
        content: str = response["message"]["content"].strip()
        logger.debug("LLM response (truncated): %s", content[:200])
        return content

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Ollama call failed (%s: %s). Returning empty string — caller will use heuristic fallback.",
            type(exc).__name__,
            exc,
        )
        return ""
