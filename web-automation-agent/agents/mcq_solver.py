"""
mcq_solver.py — MCQSolverAgent

Extracts multiple-choice questions from a page, uses the LLM to determine
the correct answer for each, and clicks the corresponding radio/checkbox input.

Question extraction strategy:
  - Group all radio/checkbox inputs by their ``name`` attribute.
  - For each group, attempt to find the question text from:
      1. A ``<fieldset><legend>`` ancestor
      2. The ``<label>`` of the first option in the group
      3. The nearest preceding ``<p>`` or ``<div>`` text node
  - Each group = one question.
"""

from typing import Optional

from config import settings
from utils.helpers import retry_with_backoff, safe_delay
from utils.logger import get_logger
from utils.ollama_client import ask_llm

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class MCQSolverAgent:
    """Extracts MCQ questions from a page and answers them using LLM reasoning."""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, page) -> bool:
        """
        Identify all MCQ questions, determine correct answers via LLM,
        and click the appropriate radio/checkbox inputs.

        Args:
            page: Playwright sync ``Page`` object.

        Returns:
            ``True`` if at least one question was answered, ``False`` if no
            questions were found on the page.
        """
        self.logger.info("MCQSolverAgent: solving MCQ page at %s", page.url)

        questions = self._extract_questions(page)
        if not questions:
            self.logger.warning("No MCQ questions found on the page.")
            return False

        self.logger.info("Found %d question(s).", len(questions))
        answered = 0

        for idx, q in enumerate(questions, start=1):
            self.logger.info(
                "Q%d: %s",
                idx,
                q["question_text"][:100] if q["question_text"] else "(no text)",
            )

            answer_idx = self._ask_llm_for_answer(q["question_text"], q["options"])
            if answer_idx is None:
                self.logger.warning("Q%d: Could not determine answer — skipping.", idx)
                continue

            chosen = q["options"][answer_idx]
            self.logger.info(
                "Q%d: Choosing option %d — '%s'",
                idx,
                answer_idx,
                chosen.get("label", "")[:80],
            )
            if self._click_answer(chosen):
                answered += 1
                safe_delay(0.3)

        self.logger.info("Answered %d/%d question(s).", answered, len(questions))
        return answered > 0

    # ------------------------------------------------------------------
    # Question extraction
    # ------------------------------------------------------------------

    def _extract_questions(self, page) -> list[dict]:
        """
        Parse the DOM for MCQ question groups.

        Returns a list of dicts, each with:
            question_text — str (may be "" if not found)
            options       — list[{value, label, locator}]
            input_type    — 'radio' | 'checkbox'
            group_name    — the shared ``name`` attribute of the inputs
        """
        questions: list[dict] = []

        try:
            inputs = page.query_selector_all("input[type=radio], input[type=checkbox]")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to query radio/checkbox inputs: %s", exc)
            return questions

        # Group inputs by name attribute
        groups: dict[str, list] = {}
        for inp in inputs:
            try:
                name = inp.get_attribute("name") or ""
                if name not in groups:
                    groups[name] = []
                groups[name].append(inp)
            except Exception:  # noqa: BLE001
                continue

        for group_name, group_inputs in groups.items():
            if not group_inputs:
                continue

            input_type = group_inputs[0].get_attribute("type") or "radio"
            question_text = self._resolve_question_text(page, group_inputs[0], group_name)
            options = self._build_options(page, group_inputs)

            if not options:
                continue

            questions.append(
                {
                    "question_text": question_text,
                    "options": options,
                    "input_type": input_type,
                    "group_name": group_name,
                }
            )

        return questions

    def _resolve_question_text(self, page, first_input, group_name: str) -> str:
        """
        Attempt to find the question text associated with a radio/checkbox group.

        Search order:
          1. ``<fieldset> > <legend>`` ancestor
          2. ``<label>`` whose ``for`` matches the first input's id
          3. Nearest preceding sibling ``<p>`` or heading text in the DOM

        Args:
            page:        Playwright Page.
            first_input: ElementHandle of the first input in the group.
            group_name:  The ``name`` attribute of the group.

        Returns:
            Question text string, or "" if not found.
        """
        # 1. Look for a <fieldset> ancestor with a <legend>
        try:
            legend = first_input.evaluate(
                """el => {
                    const fs = el.closest('fieldset');
                    if (fs) {
                        const leg = fs.querySelector('legend');
                        return leg ? leg.innerText.trim() : '';
                    }
                    return '';
                }"""
            )
            if legend:
                return legend
        except Exception:  # noqa: BLE001
            pass

        # 2. Look for a <label> associated with the first input's id
        try:
            inp_id = first_input.get_attribute("id")
            if inp_id:
                label_el = page.query_selector(f"label[for='{inp_id}']")
                if label_el:
                    text = (label_el.inner_text() or "").strip()
                    if text:
                        return text
        except Exception:  # noqa: BLE001
            pass

        # 3. Walk up the DOM and find preceding text content
        try:
            preceding_text = first_input.evaluate(
                """el => {
                    // Walk up at most 4 levels to find a parent with text siblings
                    let node = el.parentElement;
                    for (let i = 0; i < 4; i++) {
                        if (!node) break;
                        // Look for a preceding sibling that is a block element with text
                        let sib = node.previousElementSibling;
                        if (sib) {
                            const text = sib.innerText ? sib.innerText.trim() : '';
                            if (text.length > 3) return text;
                        }
                        node = node.parentElement;
                    }
                    return '';
                }"""
            )
            if preceding_text:
                return preceding_text
        except Exception:  # noqa: BLE001
            pass

        return f"Question (group: {group_name})"

    def _build_options(self, page, inputs: list) -> list[dict]:
        """
        Build option descriptors for a group of radio/checkbox inputs.

        Each option dict contains:
            value   — the ``value`` attribute
            label   — visible label text
            locator — Playwright Locator that can be clicked

        Args:
            page:   Playwright Page.
            inputs: List of ElementHandles for the option inputs.

        Returns:
            List of option descriptor dicts.
        """
        options = []
        for inp in inputs:
            try:
                value = inp.get_attribute("value") or ""
                inp_id = inp.get_attribute("id") or ""
                inp_name = inp.get_attribute("name") or ""

                # Resolve label text
                label_text = ""
                if inp_id:
                    label_el = page.query_selector(f"label[for='{inp_id}']")
                    if label_el:
                        label_text = (label_el.inner_text() or "").strip()
                if not label_text:
                    # Try the input's own aria-label
                    label_text = inp.get_attribute("aria-label") or value

                # Build a stable locator
                if inp_id:
                    locator = page.locator(f"#{inp_id}").first
                elif value and inp_name:
                    locator = page.locator(
                        f"input[name='{inp_name}'][value='{value}']"
                    ).first
                else:
                    continue  # Cannot build a reliable locator — skip

                options.append(
                    {"value": value, "label": label_text, "locator": locator}
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.debug("Skipping option due to error: %s", exc)

        return options

    # ------------------------------------------------------------------
    # LLM answering
    # ------------------------------------------------------------------

    def _ask_llm_for_answer(
        self, question_text: str, options: list[dict]
    ) -> Optional[int]:
        """
        Ask the LLM which option is correct and return its 0-based index.

        Args:
            question_text: The question string.
            options:       List of option dicts (with at least a ``label`` key).

        Returns:
            0-based integer index of the correct option, or ``None`` if the LLM
            response cannot be parsed or is out of bounds.
        """
        formatted_options = "\n".join(
            f"{i}. {opt['label']}" for i, opt in enumerate(options)
        )
        prompt = (
            f"Question: {question_text}\n\n"
            f"Options:\n{formatted_options}\n\n"
            "Which option is correct? Reply with ONLY the option number (0-based index). "
            "No explanation."
        )
        system = "You are a quiz solver. Reply with only the number of the correct option."

        result = retry_with_backoff(
            lambda: ask_llm(prompt, system=system),
            max_retries=2,
        )

        if not result:
            return None

        try:
            idx = int(result.strip().split()[0])  # take first token in case of trailing text
        except (ValueError, IndexError):
            self.logger.warning("LLM returned non-integer answer: '%s'", result[:60])
            return None

        if idx < 0 or idx >= len(options):
            self.logger.warning(
                "LLM index %d out of bounds (0–%d) — skipping.", idx, len(options) - 1
            )
            return None

        return idx

    # ------------------------------------------------------------------
    # Clicking
    # ------------------------------------------------------------------

    def _click_answer(self, option: dict) -> bool:
        """
        Click the radio or checkbox for the selected option.

        Args:
            option: Option descriptor dict with a ``locator`` key.

        Returns:
            ``True`` on success, ``False`` on Playwright error.
        """
        try:
            option["locator"].click()
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "Failed to click option '%s': %s", option.get("label", "?"), exc
            )
            return False


# TODO: add pytest tests for MCQSolverAgent
