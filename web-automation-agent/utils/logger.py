"""
logger.py — Centralised logging factory.

Every module calls get_logger(__name__) to obtain a logger that writes
INFO+ to the console and DEBUG+ to a timestamped file under outputs/logs/.
All modules share the same log file within a single interpreter run.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# Shared log file path — created once on first get_logger() call.
_LOG_FILE: Optional[Path] = None


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    On first call, creates the outputs/logs/ directory and opens a timestamped
    log file that all subsequent calls will reuse.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance with console (INFO) and file (DEBUG) handlers.
    """
    global _LOG_FILE

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times for the same name.
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ------------------------------------------------------------------
    # Console handler — INFO and above
    # ------------------------------------------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # ------------------------------------------------------------------
    # File handler — DEBUG and above (shared across all modules)
    # ------------------------------------------------------------------
    if _LOG_FILE is None:
        logs_dir = Path(settings.LOGS_DIR)
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG_FILE = logs_dir / f"session_{timestamp}.log"

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
