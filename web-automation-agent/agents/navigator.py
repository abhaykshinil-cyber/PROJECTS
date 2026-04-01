"""
navigator.py — NavigatorAgent

Finds and clicks the forward navigation button on a page (Next, Continue,
Submit, etc.), then waits for the next page to reach a stable state.

Returns True if navigation occurred, False if no suitable button was found
(signalling the end of the automation flow to the controller).
"""

import re
from typing import Optional

from config import settings
from utils.helpers import safe_delay, save_screenshot
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class NavigatorAgent:
    """Detects and clicks navigation buttons, handling page transitions and waits."""

    # Text patterns tried in priority order (longest → shortest helps prefer
    # "next page" over "next" when both are present).
    BUTTON_TEXTS: list[str] = [
        "next page",
        "next",
        "continue",
        "proceed",
        "submit",
        "finish",
        "done",
        "go",
        "forward",
    ]

    # CSS selectors for explicit submit controls (checked before text matching)
    _SUBMIT_SELECTORS = [
        "input[type=submit]",
        "button[type=submit]",
    ]

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def navigate(self, page, take_screenshot: bool = False) -> bool:
        """
        Find and click the best navigation button on the page.

        Search order:
          1. ``input[type=submit]``
          2. ``button[type=submit]``
          3. Buttons / links whose visible text matches ``BUTTON_TEXTS``
             (case-insensitive, priority order)

        Args:
            page:            Playwright sync ``Page`` object.
            take_screenshot: If ``True``, save a debug screenshot after
                             navigation.

        Returns:
            ``True`` if a navigation button was found and clicked.
            ``False`` if no button was found (end of automation flow).
        """
        self.logger.info("NavigatorAgent: looking for navigation button on %s", page.url)

        locator = self._find_nav_button(page)
        if locator is None:
            self.logger.info("No navigation button found — end of flow.")
            return False

        try:
            locator.click()
            self.logger.info("Clicked navigation button.")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to click navigation button: %s", exc)
            return False

        self._wait_for_stable(page)

        if take_screenshot:
            save_screenshot(page, label="after_navigation")

        return True

    # ------------------------------------------------------------------
    # Button discovery
    # ------------------------------------------------------------------

    def _find_nav_button(self, page) -> Optional[object]:
        """
        Return the first matching navigation locator, or ``None``.

        Tries explicit submit selectors first, then text-based matching
        against ``BUTTON_TEXTS``.

        Args:
            page: Playwright sync ``Page`` object.

        Returns:
            A Playwright Locator, or ``None`` if nothing matched.
        """
        # 1. Explicit submit controls
        for selector in self._SUBMIT_SELECTORS:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0 and loc.is_visible():
                    self.logger.debug("Found submit control via selector: %s", selector)
                    return loc
            except Exception:  # noqa: BLE001
                continue

        # 2. Text-based search across button and link elements
        for text in self.BUTTON_TEXTS:
            pattern = re.compile(rf"^\s*{re.escape(text)}\s*$", re.IGNORECASE)
            try:
                loc = page.locator("button, a, input[type=button]").filter(
                    has_text=pattern
                ).first
                if loc.count() > 0 and loc.is_visible():
                    self.logger.debug("Found navigation button with text: '%s'", text)
                    return loc
            except Exception:  # noqa: BLE001
                continue

        # 3. Broader text search (partial match) as last resort
        for text in self.BUTTON_TEXTS:
            pattern = re.compile(text, re.IGNORECASE)
            try:
                loc = page.locator("button, a").filter(has_text=pattern).first
                if loc.count() > 0 and loc.is_visible():
                    self.logger.debug(
                        "Found navigation button (partial match) with text: '%s'", text
                    )
                    return loc
            except Exception:  # noqa: BLE001
                continue

        return None

    # ------------------------------------------------------------------
    # Wait helpers
    # ------------------------------------------------------------------

    def _wait_for_stable(self, page) -> None:
        """
        Wait for the page to reach ``networkidle`` state, then apply a
        short configurable delay.

        ``TimeoutError`` is caught and logged as a warning so that slow pages
        do not abort the automation run.

        Args:
            page: Playwright sync ``Page`` object.
        """
        try:
            page.wait_for_load_state(
                "networkidle", timeout=settings.NAVIGATION_TIMEOUT
            )
            self.logger.debug("Page reached networkidle state.")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "Timed out waiting for networkidle (%s) — continuing anyway.", exc
            )

        safe_delay(settings.WAIT_AFTER_ACTION)


# TODO: add pytest tests for NavigatorAgent
