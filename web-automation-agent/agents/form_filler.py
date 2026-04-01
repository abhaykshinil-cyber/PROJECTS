"""
form_filler.py — FormFillerAgent

Detects all visible input fields on a form page, resolves values from
user-supplied data or the LLM, fills them using Playwright, then submits.

Value resolution order per field:
  1. user_data dict (keyed by field name, label, or placeholder)
  2. LLM-generated realistic value
  3. Skip (log a warning, leave blank)
"""

from typing import Optional

from config import settings
from utils.helpers import retry_with_backoff, safe_delay
from utils.logger import get_logger
from utils.ollama_client import ask_llm

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class FormFillerAgent:
    """Fills form fields on a page using a user_data dict or LLM fallback."""

    # Selectors for fillable fields (hidden inputs are excluded)
    _TEXT_INPUT_SELECTOR = (
        "input:not([type=hidden]):not([type=radio]):not([type=checkbox])"
        ":not([type=submit]):not([type=button]):not([type=reset])"
        ":not([type=image]):not([type=file])"
    )
    _SELECT_SELECTOR = "select"
    _TEXTAREA_SELECTOR = "textarea"

    # Selectors tried in order when looking for a submit button
    _SUBMIT_SELECTORS = [
        "input[type=submit]",
        "button[type=submit]",
        "button:has-text('Submit')",
        "button:has-text('submit')",
        "button:has-text('Send')",
        "button:has-text('Finish')",
        "button:has-text('Done')",
    ]

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fill(self, page, user_data: Optional[dict] = None) -> bool:
        """
        Locate and fill all visible form fields, then attempt submission.

        Args:
            page:      Playwright sync ``Page`` object.
            user_data: Dict mapping field names / labels / placeholders to
                       values. Used first; LLM is called only for unmapped
                       fields.

        Returns:
            ``True`` if the form was submitted without error, ``False`` otherwise.
        """
        if user_data is None:
            user_data = {}

        self.logger.info("FormFillerAgent: filling form on %s", page.url)

        fields = self._get_fields(page)
        if not fields:
            self.logger.warning("No fillable fields found on the page.")
            return False

        self.logger.info("Found %d fillable field(s).", len(fields))

        for field in fields:
            value = self._resolve_value(field, user_data)
            if value is None:
                self.logger.warning(
                    "No value resolved for field '%s' — skipping.",
                    field.get("name") or field.get("placeholder") or "(unnamed)",
                )
                continue
            self._fill_field(field["locator"], field["element_type"], value)
            safe_delay(0.3)  # brief pause between fields for realism

        return self._submit(page)

    # ------------------------------------------------------------------
    # Field discovery
    # ------------------------------------------------------------------

    def _get_fields(self, page) -> list[dict]:
        """
        Return a list of field descriptor dicts for all visible fillable fields.

        Each dict contains:
            locator      — Playwright Locator
            element_type — 'text' | 'email' | 'number' | 'select' | 'textarea'
            name         — value of the ``name`` attribute (or "")
            placeholder  — value of the ``placeholder`` attribute (or "")
            label        — associated ``<label>`` text (or "")
            options      — list of {value, text} dicts for <select> elements

        Returns:
            List of field descriptor dicts.
        """
        fields: list[dict] = []

        # Text-like inputs
        try:
            for el in page.query_selector_all(self._TEXT_INPUT_SELECTOR):
                if not el.is_visible():
                    continue
                locator = page.locator(
                    f"#{el.get_attribute('id')}" if el.get_attribute("id")
                    else self._TEXT_INPUT_SELECTOR
                ).first
                # Re-use the element handle directly for attribute extraction
                fields.append(
                    self._describe_element(page, el, "text", locator)
                )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Error collecting text inputs: %s", exc)

        # <select> dropdowns
        try:
            for el in page.query_selector_all(self._SELECT_SELECTOR):
                if not el.is_visible():
                    continue
                options = self._get_select_options(el)
                desc = self._describe_element(page, el, "select", None)
                desc["options"] = options
                # Build a stable locator for the select
                sel_id = el.get_attribute("id")
                sel_name = el.get_attribute("name")
                if sel_id:
                    desc["locator"] = page.locator(f"select#{sel_id}").first
                elif sel_name:
                    desc["locator"] = page.locator(f"select[name='{sel_name}']").first
                else:
                    desc["locator"] = page.locator("select").first
                fields.append(desc)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Error collecting select elements: %s", exc)

        # <textarea> fields
        try:
            for el in page.query_selector_all(self._TEXTAREA_SELECTOR):
                if not el.is_visible():
                    continue
                fields.append(
                    self._describe_element(page, el, "textarea", None)
                )
                # Build locator
                ta_id = el.get_attribute("id")
                ta_name = el.get_attribute("name")
                if ta_id:
                    fields[-1]["locator"] = page.locator(f"textarea#{ta_id}").first
                elif ta_name:
                    fields[-1]["locator"] = page.locator(
                        f"textarea[name='{ta_name}']"
                    ).first
                else:
                    fields[-1]["locator"] = page.locator("textarea").first
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Error collecting textarea elements: %s", exc)

        return fields

    def _describe_element(self, page, el, element_type: str, locator) -> dict:
        """
        Build a descriptor dict for a DOM element.

        Args:
            page:         Playwright Page.
            el:           ElementHandle.
            element_type: Field type string.
            locator:      Pre-built Locator or None.

        Returns:
            Descriptor dict.
        """
        name = el.get_attribute("name") or ""
        placeholder = el.get_attribute("placeholder") or ""
        el_id = el.get_attribute("id") or ""
        input_type = el.get_attribute("type") or element_type

        # Resolve associated label text
        label_text = ""
        if el_id:
            try:
                label_el = page.query_selector(f"label[for='{el_id}']")
                if label_el:
                    label_text = (label_el.inner_text() or "").strip()
            except Exception:  # noqa: BLE001
                pass

        # Build a default locator if none provided
        if locator is None:
            if el_id:
                locator = page.locator(f"#{el_id}").first
            elif name:
                locator = page.locator(f"[name='{name}']").first
            else:
                locator = page.locator(element_type).first

        return {
            "locator": locator,
            "element_type": input_type,
            "name": name,
            "placeholder": placeholder,
            "label": label_text,
            "options": [],
        }

    def _get_select_options(self, el) -> list[dict]:
        """
        Extract all options from a <select> element.

        Returns:
            List of {value, text} dicts.
        """
        try:
            option_els = el.query_selector_all("option")
            return [
                {
                    "value": o.get_attribute("value") or "",
                    "text": (o.inner_text() or "").strip(),
                }
                for o in option_els
            ]
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------------
    # Value resolution
    # ------------------------------------------------------------------

    def _resolve_value(self, field: dict, user_data: dict) -> Optional[str]:
        """
        Determine what value to fill for a field.

        Checks ``user_data`` first (by name → label → placeholder), then
        delegates to the LLM.

        Args:
            field:     Field descriptor dict from ``_get_fields``.
            user_data: User-supplied mapping of field identifiers to values.

        Returns:
            A string value to fill, or ``None`` if nothing could be determined.
        """
        for key in (field["name"], field["label"], field["placeholder"]):
            if key and key in user_data:
                self.logger.debug("Using user_data value for key '%s'.", key)
                return str(user_data[key])

        # Fallback to LLM
        return self._ask_llm_for_value(field)

    def _ask_llm_for_value(self, field: dict) -> Optional[str]:
        """
        Ask the LLM to generate an appropriate value for a form field.

        Args:
            field: Field descriptor dict.

        Returns:
            LLM-generated value string, or ``None`` if the response is empty.
        """
        options_str = (
            ", ".join(f"{o['text']}" for o in field["options"])
            if field["options"]
            else "N/A"
        )
        prompt = (
            f"Field name: {field['name'] or 'unknown'}.\n"
            f"Field type: {field['element_type']}.\n"
            f"Placeholder: {field['placeholder'] or 'none'}.\n"
            f"Label: {field['label'] or 'none'}.\n"
            f"Available options: {options_str}.\n\n"
            "Provide a realistic value for this form field. "
            "Reply with ONLY the value — no explanation, no quotes."
        )
        system = "You are a form-filling assistant. Reply with only the field value."

        result = retry_with_backoff(
            lambda: ask_llm(prompt, system=system),
            max_retries=2,
        )

        if result and result.strip():
            self.logger.debug(
                "LLM value for field '%s': %s",
                field.get("name") or field.get("label") or "(unnamed)",
                result[:80],
            )
            return result.strip()

        return None

    # ------------------------------------------------------------------
    # Field filling
    # ------------------------------------------------------------------

    def _fill_field(self, locator, element_type: str, value: str) -> bool:
        """
        Fill a single field using the appropriate Playwright method.

        Args:
            locator:      Playwright Locator pointing to the field.
            element_type: Field type string.
            value:        Value to fill.

        Returns:
            ``True`` on success, ``False`` on Playwright error.
        """
        try:
            if element_type == "select":
                locator.select_option(value)
            elif element_type in ("checkbox", "radio"):
                locator.check()
            else:
                locator.fill(value)
            self.logger.debug("Filled '%s' field with: %s", element_type, value[:60])
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to fill %s field: %s", element_type, exc)
            return False

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def _submit(self, page) -> bool:
        """
        Find and click the form's submit button.

        Tries selectors in the order defined by ``_SUBMIT_SELECTORS``.

        Args:
            page: Playwright sync ``Page`` object.

        Returns:
            ``True`` if a submit button was found and clicked, ``False`` otherwise.
        """
        for selector in self._SUBMIT_SELECTORS:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    self.logger.info("Form submitted via selector: %s", selector)
                    return True
            except Exception as exc:  # noqa: BLE001
                self.logger.debug("Submit selector '%s' failed: %s", selector, exc)

        self.logger.warning("No submit button found — form not submitted.")
        return False


# TODO: add pytest tests for FormFillerAgent
