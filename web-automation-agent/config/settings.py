"""
settings.py — Single source of truth for all configuration constants.

All values are overridable via environment variables or a .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (web-automation-agent/) if present
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Ollama / LLM
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# ---------------------------------------------------------------------------
# Automation loop limits
# ---------------------------------------------------------------------------

MAX_PAGES: int = int(os.getenv("MAX_PAGES", 20))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", 3))

# ---------------------------------------------------------------------------
# Playwright timeouts and delays
# ---------------------------------------------------------------------------

NAVIGATION_TIMEOUT: int = int(os.getenv("NAVIGATION_TIMEOUT", 30000))  # milliseconds
WAIT_AFTER_ACTION: float = float(os.getenv("WAIT_AFTER_ACTION", 1.5))  # seconds

# ---------------------------------------------------------------------------
# Browser behaviour
# ---------------------------------------------------------------------------

HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
DEBUG_SCREENSHOTS: bool = os.getenv("DEBUG_SCREENSHOTS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# LLM context limits
# ---------------------------------------------------------------------------

LLM_CONTEXT_MAX_CHARS: int = int(os.getenv("LLM_CONTEXT_MAX_CHARS", 3000))

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

SESSION_STATE_PATH: str = os.getenv("SESSION_STATE_PATH", "outputs/session_state.json")
SCREENSHOTS_DIR: str = os.getenv("SCREENSHOTS_DIR", "outputs/screenshots")
LOGS_DIR: str = os.getenv("LOGS_DIR", "outputs/logs")
