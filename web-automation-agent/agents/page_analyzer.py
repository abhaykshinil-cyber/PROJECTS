"""
page_analyzer.py — PageAnalyzerAgent

Classifies a loaded Playwright page as FORM, MCQ, or UNKNOWN.

Strategy:
  1. Count interactive element types for heuristic context.
  2. Extract truncated DOM text.
  3. Ask the LLM with a short, deterministic prompt.
  4. Parse the response; fall back to a simple heuristic if the LLM fails
     or returns an unexpected answer.
"""

from enum import Enum
from typing import Optional

from config import settings
from utils.helpers import extract_dom_text, retry_with_backoff
from utils.logger import get_logger
from utils.ollama_client import ask_llm

# ---------------------------------------------------------------------------
# Page type enum
# ---------------------------------------------------------------------------


class PageType(str, Enum):
    """Possible classifications for a web page."""

    FORM = "FORM"
    MCQ = "MCQ"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PageAnalyzerAgent:
    """Classifies a web page as FORM, MCQ, or UNKNOWN using LLM + heuristic fallback."""

    # CSS selectors used for element counting
    _FORM_INPUT_SELECTOR = (
        "input:not([type=hidden]):not([type=radio]):not([type=checkbox]),"
        " select, textarea"
    )
    _RADIO_SELECTOR = "input[type=radio], input[type=checkbox]"

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, page) -> PageType:
        """
        Analyze the current page and return its type.

        Args:
            page: Playwright sync ``Page`` object.

        Returns:
            ``PageType`` enum value — FORM, MCQ, or UNKNOWN.
        """
        self.logger.info("Analyzing page: %s", page.url)

        input_count, radio_count = self._count_elements(page)
        self.logger.debug(
            "Element counts — form inputs: %d, radio/checkbox: %d",
            input_count,
            radio_count,
        )

        if input_count == 0 and radio_count == 0:
            self.logger.warning("No interactive elements found — returning UNKNOWN.")
            return PageType.UNKNOWN

        dom_text = extract_dom_text(page)
        prompt = self._build_prompt(dom_text, input_count, radio_count)

        result: Optional[str] = retry_with_backoff(
            lambda: ask_llm(
                prompt,
                system="You are a web page classifier. Reply with exactly one word.",
            ),
            max_retries=2,
        )

        if result:
            parsed = result.strip().upper()
            if parsed in (PageType.FORM.value, PageType.MCQ.value):
                self.logger.info("LLM classified page as: %s", parsed)
                return PageType(parsed)
            self.logger.warning(
                "LLM returned unexpected value '%s' — using heuristic fallback.", parsed
            )
        else:
            self.logger.warning("LLM returned empty response — using heuristic fallback.")

        return self._heuristic_fallback(input_count, radio_count)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _count_elements(self, page) -> tuple[int, int]:
        """
        Count interactive form elements on the page.

        Returns:
            Tuple of (form_input_count, radio_checkbox_count).
        """
        try:
            form_inputs = len(page.query_selector_all(self._FORM_INPUT_SELECTOR))
            radios = len(page.query_selector_all(self._RADIO_SELECTOR))
            return form_inputs, radios
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("_count_elements failed: %s", exc)
            return 0, 0

    def _build_prompt(
        self, dom_text: str, input_count: int, radio_count: int
    ) -> str:
        """Build the classification prompt sent to the LLM."""
        return (
            f"Page content (truncated):\n{dom_text}\n\n"
            f"Text/number/email input fields: {input_count}. "
            f"Radio/checkbox inputs: {radio_count}.\n\n"
            "Is this page a FORM (fields to fill in) or MCQ (multiple-choice questions)? "
            "Reply with exactly one word: FORM or MCQ."
        )

    def _heuristic_fallback(self, input_count: int, radio_count: int) -> PageType:
        """
        Simple rule-based classification used when the LLM is unavailable.

        Logic:
          - More radio/checkbox inputs than text inputs → MCQ
          - More text inputs → FORM
          - Equal and non-zero → FORM (safer default)
          - Both zero → UNKNOWN

        Args:
            input_count: Number of text/select/textarea inputs.
            radio_count: Number of radio/checkbox inputs.

        Returns:
            ``PageType`` enum value.
        """
        if input_count == 0 and radio_count == 0:
            return PageType.UNKNOWN
        if radio_count > input_count:
            self.logger.info("Heuristic classified page as: MCQ")
            return PageType.MCQ
        self.logger.info("Heuristic classified page as: FORM")
        return PageType.FORM


# TODO: add pytest tests for PageAnalyzerAgent
