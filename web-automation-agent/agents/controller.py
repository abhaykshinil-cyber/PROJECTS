"""
controller.py — ControllerAgent

Orchestrates the full web automation loop:
  launch browser → analyze page → act (fill/solve) → navigate → repeat.

This is the only file that touches the Playwright browser lifecycle.
All other agents receive the live ``Page`` object and interact with the DOM
through it.

Session state is persisted to ``outputs/session_state.json`` after each step
so that progress is not lost if the run is interrupted.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, Page, sync_playwright

from agents.form_filler import FormFillerAgent
from agents.mcq_solver import MCQSolverAgent
from agents.navigator import NavigatorAgent
from agents.page_analyzer import PageAnalyzerAgent, PageType
from config import settings
from utils.helpers import safe_delay
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ControllerAgent:
    """
    Orchestrates the web automation loop.

    Creates sub-agents internally and passes the shared Playwright ``Page``
    object to each one in turn. Manages browser lifecycle, retry logic,
    stuck-loop detection, and session state persistence.
    """

    def __init__(
        self,
        headless: bool = settings.HEADLESS,
        debug_screenshots: bool = settings.DEBUG_SCREENSHOTS,
        max_pages: int = settings.MAX_PAGES,
        max_retries: int = settings.MAX_RETRIES,
    ) -> None:
        """
        Initialise the controller and all sub-agents.

        Args:
            headless:          Run the browser in headless mode.
            debug_screenshots: Save screenshots after each navigation step.
            max_pages:         Maximum number of pages to process before stopping.
            max_retries:       Maximum consecutive failures before aborting.
        """
        self.headless = headless
        self.debug_screenshots = debug_screenshots
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.logger = get_logger(__name__)

        # Sub-agents
        self.analyzer = PageAnalyzerAgent()
        self.filler = FormFillerAgent()
        self.solver = MCQSolverAgent()
        self.navigator = NavigatorAgent()

        # Session state (persisted to JSON after each step)
        self._state: dict = self._default_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        url: str,
        mode: str = "auto",
        user_data: Optional[dict] = None,
    ) -> None:
        """
        Main entry point. Launches the browser, runs the automation loop,
        and closes the browser when done.

        Args:
            url:       Target URL to start from.
            mode:      Page handling mode — ``'form'``, ``'mcq'``, or ``'auto'``.
            user_data: Optional dict of form field values for ``FormFillerAgent``.
                       Keys can be field names, labels, or placeholders.
        """
        if user_data is None:
            user_data = {}

        self._load_state()
        self._state["start_url"] = url
        self._state["run_started_at"] = datetime.now().isoformat()

        self.logger.info(
            "Starting automation — URL: %s | Mode: %s | Headless: %s",
            url,
            mode,
            self.headless,
        )

        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(headless=self.headless)
            try:
                page: Page = browser.new_page()
                page.goto(url, timeout=settings.NAVIGATION_TIMEOUT)
                self.logger.info("Navigated to %s", url)
                safe_delay(settings.WAIT_AFTER_ACTION)
                self._run_loop(page, mode, user_data)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Fatal error during automation: %s", exc)
            finally:
                browser.close()
                self.logger.info("Browser closed.")

        self._save_state()
        self.logger.info(
            "Automation complete. Pages processed: %d", self._state["page_number"]
        )

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _run_loop(self, page: Page, mode: str, user_data: dict) -> None:
        """
        Core automation loop: analyze → act → navigate, up to ``max_pages``
        iterations.

        Loop exits when:
          - ``NavigatorAgent.navigate()`` returns ``False`` (no next button)
          - Consecutive failures reach ``max_retries``
          - The current URL equals the previous URL after navigation (stuck)
          - ``max_pages`` is reached

        Args:
            page:      Playwright ``Page`` object.
            mode:      Handling mode — 'form' | 'mcq' | 'auto'.
            user_data: Form field data forwarded to ``FormFillerAgent``.
        """
        consecutive_failures = 0

        for page_num in range(1, self.max_pages + 1):
            self._state["page_number"] = page_num
            previous_url = page.url
            self.logger.info("--- Page %d: %s ---", page_num, previous_url)

            # ---- Determine page type ----
            try:
                if mode == "auto":
                    page_type = self.analyzer.analyze(page)
                elif mode == "form":
                    page_type = PageType.FORM
                else:
                    page_type = PageType.MCQ
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Page analysis failed: %s", exc)
                consecutive_failures += 1
                if consecutive_failures >= self.max_retries:
                    self.logger.error("Max consecutive failures reached — aborting.")
                    break
                continue

            # ---- Act on the page ----
            try:
                success = self._act(page, page_type, mode, user_data)
                if not success:
                    self.logger.warning("Action on page %d reported failure.", page_num)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Action failed on page %d: %s", page_num, exc)
                success = False

            self._record_action(page_type.value, success, previous_url)

            # ---- Navigate forward ----
            try:
                navigated = self.navigator.navigate(
                    page, take_screenshot=self.debug_screenshots
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Navigation failed on page %d: %s", page_num, exc)
                consecutive_failures += 1
                if consecutive_failures >= self.max_retries:
                    self.logger.error("Max consecutive failures reached — aborting.")
                    break
                continue

            if not navigated:
                self.logger.info("No navigation button found — flow complete.")
                break

            # ---- Stuck-loop guard ----
            if page.url == previous_url:
                self.logger.warning(
                    "URL unchanged after navigation (%s) — possible stuck loop. Aborting.",
                    previous_url,
                )
                break

            self._state["current_url"] = page.url
            consecutive_failures = 0  # reset on successful iteration

        else:
            self.logger.info("Reached max_pages limit (%d).", self.max_pages)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def _act(self, page: Page, page_type: PageType, mode: str, user_data: dict) -> bool:
        """
        Dispatch to the correct sub-agent based on ``page_type`` and ``mode``.

        Args:
            page:      Playwright ``Page`` object.
            page_type: Classification result from ``PageAnalyzerAgent``.
            mode:      Explicit mode override (or 'auto').
            user_data: Form field data.

        Returns:
            ``True`` if the action reported success, ``False`` otherwise.
        """
        if page_type == PageType.FORM or mode == "form":
            self.logger.info("Dispatching to FormFillerAgent.")
            return self.filler.fill(page, user_data)

        if page_type == PageType.MCQ or mode == "mcq":
            self.logger.info("Dispatching to MCQSolverAgent.")
            return self.solver.solve(page)

        # PageType.UNKNOWN — log and fall through to navigation
        self.logger.warning(
            "Page type UNKNOWN — skipping fill/solve, attempting navigation only."
        )
        return False

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _default_state(self) -> dict:
        """Return a clean session state dict."""
        return {
            "start_url": "",
            "current_url": "",
            "page_number": 0,
            "run_started_at": "",
            "actions": [],   # list of {page_number, url, page_type, success, timestamp}
            "answers": {},   # question_text → chosen option label (populated by MCQSolverAgent consumers)
        }

    def _load_state(self) -> None:
        """
        Load a previous session state from ``SESSION_STATE_PATH`` if it exists.

        Silently resets to a clean state if the file is absent or corrupted.
        """
        path = Path(settings.SESSION_STATE_PATH)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self._state.update(loaded)
            self.logger.info("Session state loaded from %s", path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "Could not load session state (%s) — starting fresh.", exc
            )
            self._state = self._default_state()

    def _save_state(self) -> None:
        """Persist the current session state to ``SESSION_STATE_PATH``."""
        path = Path(settings.SESSION_STATE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
            self.logger.debug("Session state saved to %s", path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to save session state: %s", exc)

    def _record_action(self, page_type: str, result: bool, url: str) -> None:
        """
        Append an action record to the session state and persist immediately.

        Args:
            page_type: String representation of the ``PageType`` value.
            result:    Whether the action succeeded.
            url:       URL of the page at the time of action.
        """
        record = {
            "page_number": self._state["page_number"],
            "url": url,
            "page_type": page_type,
            "success": result,
            "timestamp": datetime.now().isoformat(),
        }
        self._state["actions"].append(record)
        self._save_state()


# TODO: add pytest tests for ControllerAgent
