"""
helpers.py — Cross-cutting utility functions shared by all agents.

Provides retry logic, DOM text extraction, safe delays, and screenshot capture.
All functions are synchronous — Playwright's sync API is used throughout.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TypeVar

from config import settings
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Module setup
# ---------------------------------------------------------------------------

logger = get_logger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


def retry_with_backoff(
    fn: Callable[[], T],
    max_retries: int = settings.MAX_RETRIES,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
) -> Optional[T]:
    """
    Call ``fn()`` up to ``max_retries`` times with exponential back-off.

    Args:
        fn:           Zero-argument callable to attempt.
        max_retries:  Total number of attempts before giving up.
        base_delay:   Initial sleep in seconds; doubles on each subsequent retry.
        exceptions:   Tuple of exception types that should trigger a retry.
                      All other exceptions propagate immediately.

    Returns:
        The return value of ``fn()`` on success, or ``None`` if every attempt
        raises one of the specified exceptions.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except exceptions as exc:  # type: ignore[misc]
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                attempt,
                max_retries,
                exc,
                delay,
            )
            if attempt < max_retries:
                time.sleep(delay)

    logger.error("All %d attempts failed. Last error: %s", max_retries, last_exc)
    return None


# ---------------------------------------------------------------------------
# DOM utilities
# ---------------------------------------------------------------------------


def extract_dom_text(page, max_chars: int = settings.LLM_CONTEXT_MAX_CHARS) -> str:
    """
    Extract readable text from the page body and truncate to ``max_chars``.

    Uses Playwright's ``inner_text('body')`` which returns only visible text,
    stripping tags, scripts, and styles. Excess whitespace is collapsed.

    Args:
        page:      Playwright sync ``Page`` object.
        max_chars: Maximum number of characters to return.

    Returns:
        Truncated plain-text string, or ``""`` on Playwright error.
    """
    try:
        raw: str = page.inner_text("body")
        # Collapse multiple blank lines / leading spaces
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        if len(cleaned) > max_chars:
            logger.debug(
                "DOM text truncated from %d to %d chars.", len(cleaned), max_chars
            )
        return cleaned[:max_chars]
    except Exception as exc:  # noqa: BLE001
        logger.warning("extract_dom_text failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


def safe_delay(seconds: float = settings.WAIT_AFTER_ACTION) -> None:
    """
    Synchronous sleep used between Playwright actions to avoid race conditions.

    Args:
        seconds: Duration to sleep (default: ``settings.WAIT_AFTER_ACTION``).
    """
    logger.debug("Waiting %.1f seconds…", seconds)
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------


def save_screenshot(
    page,
    label: str,
    directory: str = settings.SCREENSHOTS_DIR,
) -> Optional[str]:
    """
    Save a full-page screenshot to ``directory`` with a timestamped filename.

    Args:
        page:      Playwright sync ``Page`` object.
        label:     Human-readable label included in the filename (spaces replaced
                   with underscores).
        directory: Output directory path (created if it does not exist).

    Returns:
        Absolute path to the saved file as a string, or ``None`` on failure.
    """
    try:
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = label.replace(" ", "_")
        filepath = out_dir / f"{safe_label}_{timestamp}.png"
        page.screenshot(path=str(filepath), full_page=True)
        logger.info("Screenshot saved: %s", filepath)
        return str(filepath.resolve())
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_screenshot failed: %s", exc)
        return None
