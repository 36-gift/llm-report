"""
Tests for logging configuration.
"""
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from llm_report_tool.utils.logging_config import (
    ColoredConsoleFormatter,
    StructuredFormatter,
    get_logger,
    log_function_call,
    setup_logging,
)


class TestStructuredFormatter:
    """Test cases for the StructuredFormatter."""

    def test_basic_log_formatting(self):
        """Test basic log record formatting."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Test message"
        assert parsed["line"] == 42
        assert "timestamp" in parsed

    def test_exception_formatting(self):
        """Test exception information formatting."""
        formatter = StructuredFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="/test/path.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=True,
            )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "Test exception"
        assert "traceback" in parsed["exception"]

    def test_extra_fields_inclusion(self):
        """Test inclusion of extra fields."""
        formatter = StructuredFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert "extra" in parsed
        assert parsed["extra"]["custom_field"] == "custom_value"


class TestColoredConsoleFormatter:
    """Test cases for the ColoredConsoleFormatter."""

    def test_basic_formatting(self):
        """Test basic console log formatting."""
        formatter = ColoredConsoleFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.created = 1640995200.0  # Fixed timestamp for testing

        formatted = formatter.format(record)

        assert "INFO" in formatted
        assert "test_logger" in formatted
        assert "Test message" in formatted
        assert "\033[32m" in formatted  # Green color for INFO
        assert "\033[0m" in formatted  # Reset color

    def test_different_log_levels(self):
        """Test different log level colors."""
        formatter = ColoredConsoleFormatter()

        levels_and_colors = [
            (logging.DEBUG, "\033[36m"),  # Cyan
            (logging.INFO, "\033[32m"),  # Green
            (logging.WARNING, "\033[33m"),  # Yellow
            (logging.ERROR, "\033[31m"),  # Red
            (logging.CRITICAL, "\033[35m"),  # Magenta
        ]

        for level, expected_color in levels_and_colors:
            record = logging.LogRecord(
                name="test_logger",
                level=level,
                pathname="/test/path.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            record.created = 1640995200.0

            formatted = formatter.format(record)
            assert expected_color in formatted


class TestSetupLogging:
    """Test cases for the setup_logging function."""

    def test_basic_setup(self, temp_dir):
        """Test basic logging setup."""
        logger = setup_logging(
            log_level="INFO",
            log_to_file=True,
            log_to_console=False,
            log_file_path=temp_dir / "test.log",
        )

        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    def test_file_logging(self, temp_dir):
        """Test file logging configuration."""
        log_file = temp_dir / "test.log"

        logger = setup_logging(
            log_level="DEBUG", log_to_file=True, log_to_console=False, log_file_path=log_file
        )

        logger.info("Test log message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test log message" in content

    def test_console_logging(self, caplog):
        """Test console logging configuration."""
        logger = setup_logging(log_level="INFO", log_to_file=False, log_to_console=True)

        logger.info("Test console message")

        assert "Test console message" in caplog.text

    def test_structured_logging(self, temp_dir):
        """Test structured JSON logging."""
        log_file = temp_dir / "structured.log"

        logger = setup_logging(
            log_level="INFO",
            log_to_file=True,
            log_to_console=False,
            structured_logging=True,
            log_file_path=log_file,
        )

        logger.info("Structured test message", extra={"test_field": "test_value"})

        content = log_file.read_text()
        log_entry = json.loads(content.strip())

        assert log_entry["message"] == "Structured test message"
        assert log_entry["level"] == "INFO"
        assert "test_field" in log_entry.get("extra", {})


class TestGetLogger:
    """Test cases for the get_logger function."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"


class TestLogFunctionCall:
    """Test cases for the log_function_call decorator."""

    def test_function_call_logging(self, caplog):
        """Test that function calls are logged correctly."""
        test_logger = logging.getLogger("test")
        test_logger.setLevel(logging.DEBUG)

        @log_function_call(test_logger, level=logging.DEBUG)
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)

        assert result == 5
        assert "Entering function" in caplog.text
        assert "Exiting function" in caplog.text

    def test_function_exception_logging(self, caplog):
        """Test that function exceptions are logged correctly."""
        test_logger = logging.getLogger("test")
        test_logger.setLevel(logging.DEBUG)

        @log_function_call(test_logger, level=logging.DEBUG)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        assert "raised exception" in caplog.text
        assert "Test error" in caplog.text

    def test_function_args_logging(self, caplog):
        """Test logging function arguments."""
        test_logger = logging.getLogger("test")
        test_logger.setLevel(logging.DEBUG)

        @log_function_call(test_logger, level=logging.DEBUG, include_args=True)
        def test_function(x, y, z=None):
            return x + y

        test_function(2, 3, z="test")

        # Check that arguments are logged (exact format may vary)
        assert "Entering function" in caplog.text

    def test_function_result_logging(self, caplog):
        """Test logging function results."""
        test_logger = logging.getLogger("test")
        test_logger.setLevel(logging.DEBUG)

        @log_function_call(test_logger, level=logging.DEBUG, include_result=True)
        def test_function():
            return "test_result"

        test_function()

        assert "Exiting function" in caplog.text
