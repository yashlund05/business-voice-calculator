"""Privacy-safe logging configuration for Voice Calculator.

In normal mode:
- Logs state transitions, error codes, and performance timings only.
- Audio data, user transcripts, and numeric values are NEVER logged.

In explicit debug mode:
- Transcripts and parsed values may be logged locally for diagnostic purposes.
- All logs remain strictly local (git-ignored logs/ directory).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from voice_calculator.config import LOG_DIR_PATH

LOGGER_NAME = "voice_calculator"
DEFAULT_LOG_FILE = "app.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
BACKUP_COUNT = 3


def setup_logging(
    log_dir: Optional[Path] = None,
    log_file_name: str = DEFAULT_LOG_FILE,
    debug_mode: bool = False,
    console_output: bool = False,
) -> logging.Logger:
    """Configures and returns the application logger with privacy-safe defaults.

    Args:
        log_dir: Directory where log files are stored. Defaults to LOG_DIR_PATH.
        log_file_name: Base filename for the rotating log.
        debug_mode: If True, sets level to DEBUG. If False, sets level to INFO.
        console_output: If True, also outputs logs to stderr.

    Returns:
        Configured logging.Logger instance.
    """
    target_dir = log_dir or LOG_DIR_PATH
    logger = logging.getLogger(LOGGER_NAME)

    # Avoid adding duplicate handlers if setup is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    level = logging.DEBUG if debug_mode else logging.INFO
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — best effort: a read-only install location must
    # not prevent startup (prd.md §9: the app stays usable).
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(target_dir / log_file_name),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning("File logging unavailable (%s); continuing without file logs.", e)

    # Optional console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Retrieves the application logger."""
    return logging.getLogger(LOGGER_NAME)
