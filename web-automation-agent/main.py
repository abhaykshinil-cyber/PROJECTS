"""
main.py — CLI entry point for the Hybrid AI Web Automation Agent.

Usage:
    python main.py --url <URL> [--mode form|mcq|auto] [--headless] [--screenshot]
                   [--user-data '{"name": "Alice", "email": "alice@example.com"}']

Examples:
    # Auto-detect page type and fill/solve it:
    python main.py --url https://httpbin.org/forms/post

    # Force form-filling mode with custom data:
    python main.py --url https://example.com/signup --mode form \\
        --user-data '{"name": "Jane Doe", "email": "jane@example.com"}'

    # Solve an MCQ quiz in headless mode with debug screenshots:
    python main.py --url https://example.com/quiz --mode mcq --headless --screenshot
"""

import argparse
import json
import sys

from agents.controller import ControllerAgent
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """
    Define and parse CLI arguments.

    Returns:
        Parsed ``argparse.Namespace`` object.
    """
    parser = argparse.ArgumentParser(
        prog="web-automation-agent",
        description=(
            "Hybrid AI Web Automation Agent — automatically fills forms and "
            "solves MCQ quizzes using Playwright + Ollama (qwen3:8b)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Target URL to open and automate.",
    )
    parser.add_argument(
        "--mode",
        choices=["form", "mcq", "auto"],
        default="auto",
        help=(
            "How to handle each page. "
            "'form' always fills fields, 'mcq' always solves questions, "
            "'auto' uses the LLM to detect the page type (default: auto)."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run the browser in headless mode (no visible window).",
    )
    parser.add_argument(
        "--screenshot",
        action="store_true",
        default=False,
        help="Save a debug screenshot after each navigation step.",
    )
    parser.add_argument(
        "--user-data",
        dest="user_data",
        default=None,
        metavar="JSON",
        help=(
            "JSON string of field name/label → value mappings used by the "
            "form filler. Example: '{\"name\": \"Alice\", \"email\": \"alice@example.com\"}'"
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Parse CLI arguments, create a ``ControllerAgent``, and start the automation.
    """
    args = parse_args()

    # Parse --user-data JSON
    user_data: dict = {}
    if args.user_data:
        try:
            user_data = json.loads(args.user_data)
            if not isinstance(user_data, dict):
                raise ValueError("--user-data must be a JSON object (dict).")
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[ERROR] Invalid --user-data JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    # Print startup banner
    logger.info("=" * 60)
    logger.info("  Hybrid AI Web Automation Agent")
    logger.info("=" * 60)
    logger.info("  URL        : %s", args.url)
    logger.info("  Mode       : %s", args.mode)
    logger.info("  Headless   : %s", args.headless)
    logger.info("  Screenshots: %s", args.screenshot)
    logger.info("  User data  : %s keys provided", len(user_data))
    logger.info("=" * 60)

    controller = ControllerAgent(
        headless=args.headless,
        debug_screenshots=args.screenshot,
    )

    controller.run(url=args.url, mode=args.mode, user_data=user_data)


if __name__ == "__main__":
    main()
