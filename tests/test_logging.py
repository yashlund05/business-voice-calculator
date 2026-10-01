"""Tests for voice_calculator.logging_setup."""

import logging
from voice_calculator.logging_setup import setup_logging, get_logger, LOGGER_NAME


def test_logging_setup_file_creation(tmp_path):
    """Verify logging setup creates file and writes log lines."""
    log_dir = tmp_path / "test_logs"
    logger = setup_logging(log_dir=log_dir, log_file_name="test.log", debug_mode=False)

    assert logger.name == LOGGER_NAME
    assert logger.level == logging.INFO

    logger.info("Test info message")

    log_file = log_dir / "test.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test info message" in content
    assert "[INFO]" in content


def test_logging_debug_mode(tmp_path):
    """Verify debug mode configures DEBUG log level."""
    log_dir = tmp_path / "test_logs_debug"
    logger = setup_logging(log_dir=log_dir, log_file_name="debug.log", debug_mode=True)

    assert logger.level == logging.DEBUG
    logger.debug("Debug diagnostic message")

    log_file = log_dir / "debug.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Debug diagnostic message" in content


def test_get_logger():
    """Verify get_logger returns application logger."""
    logger = get_logger()
    assert logger.name == LOGGER_NAME
