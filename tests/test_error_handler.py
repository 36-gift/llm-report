"""
Tests for error handling utilities.
"""
import time
from unittest.mock import Mock, patch

import pytest

from llm_report_tool.exceptions import RetryExhaustedError, ScrapingError
from llm_report_tool.utils.error_handler import (
    ErrorContext,
    handle_critical_error,
    retry_with_exponential_backoff,
    safe_execute,
)


class TestRetryWithExponentialBackoff:
    """Test cases for the retry decorator."""

    def test_successful_execution(self):
        """Test that successful functions are executed normally."""

        @retry_with_exponential_backoff(max_retries=3)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_retry_on_exception(self):
        """Test that functions are retried on specified exceptions."""
        call_count = 0

        @retry_with_exponential_backoff(max_retries=2, initial_delay=0.01, exceptions=ValueError)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Test that RetryExhaustedError is raised when all retries are exhausted."""

        @retry_with_exponential_backoff(max_retries=2, initial_delay=0.01)
        def always_failing_function():
            raise ValueError("Always fails")

        with pytest.raises(RetryExhaustedError):
            always_failing_function()

    def test_custom_reraise_exception(self):
        """Test that custom exception is raised when specified."""

        @retry_with_exponential_backoff(max_retries=1, initial_delay=0.01, reraise_as=ScrapingError)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ScrapingError):
            failing_function()

    def test_exponential_backoff_timing(self):
        """Test that delays increase exponentially."""
        call_times = []

        @retry_with_exponential_backoff(max_retries=3, initial_delay=0.01, backoff_factor=2.0)
        def timing_function():
            call_times.append(time.time())
            raise ValueError("Test error")

        with pytest.raises(RetryExhaustedError):
            timing_function()

        # Check that delays are approximately correct
        assert len(call_times) == 4  # Initial call + 3 retries

        # Calculate actual delays (allowing for some tolerance)
        delays = [call_times[i + 1] - call_times[i] for i in range(len(call_times) - 1)]
        expected_delays = [0.01, 0.02, 0.04]  # exponential backoff

        for actual, expected in zip(delays, expected_delays):
            assert abs(actual - expected) < 0.005  # 5ms tolerance

    def test_on_retry_callback(self):
        """Test that retry callback is called correctly."""
        retry_calls = []

        def on_retry_callback(attempt, exception):
            retry_calls.append((attempt, str(exception)))

        @retry_with_exponential_backoff(
            max_retries=2, initial_delay=0.01, on_retry=on_retry_callback
        )
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(RetryExhaustedError):
            failing_function()

        assert len(retry_calls) == 2
        assert retry_calls[0] == (1, "Test error")
        assert retry_calls[1] == (2, "Test error")


class TestSafeExecute:
    """Test cases for the safe_execute function."""

    def test_successful_execution(self):
        """Test successful function execution."""

        def successful_function(x, y):
            return x + y

        result = safe_execute(successful_function, 2, 3)
        assert result == 5

    def test_exception_handling_with_default(self):
        """Test exception handling with default return value."""

        def failing_function():
            raise ValueError("Test error")

        result = safe_execute(failing_function, default_return="default")
        assert result == "default"

    def test_exception_reraising(self):
        """Test exception reraising when requested."""

        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            safe_execute(failing_function, reraise=True)

    def test_logging_disabled(self, caplog):
        """Test that logging can be disabled."""

        def failing_function():
            raise ValueError("Test error")

        safe_execute(failing_function, log_errors=False)
        assert "Error executing" not in caplog.text


class TestErrorContext:
    """Test cases for the ErrorContext context manager."""

    def test_successful_context(self):
        """Test context manager with no errors."""
        with ErrorContext("test context") as ctx:
            result = 1 + 1

        assert not ctx.error_occurred
        assert ctx.exception is None

    def test_error_handling_with_reraise(self):
        """Test error handling with reraising enabled."""
        with pytest.raises(ValueError):
            with ErrorContext("test context", reraise=True):
                raise ValueError("Test error")

    def test_error_suppression(self):
        """Test error suppression when reraise is False."""
        with ErrorContext("test context", reraise=False) as ctx:
            raise ValueError("Test error")

        assert ctx.error_occurred
        assert isinstance(ctx.exception, ValueError)

    def test_error_callback(self):
        """Test that error callback is called correctly."""
        callback_calls = []

        def error_callback(exception):
            callback_calls.append(str(exception))

        with ErrorContext("test context", reraise=False, on_error=error_callback):
            raise ValueError("Test error")

        assert len(callback_calls) == 1
        assert callback_calls[0] == "Test error"


class TestHandleCriticalError:
    """Test cases for critical error handling."""

    def test_critical_error_logging(self, caplog):
        """Test that critical errors are logged properly."""
        error = ValueError("Critical test error")

        handle_critical_error(error, "test context")

        assert "Critical error in test context" in caplog.text
        assert "Critical test error" in caplog.text

    @patch("sys.exit")
    def test_critical_error_exit(self, mock_exit):
        """Test that critical errors can trigger application exit."""
        error = ValueError("Critical test error")

        handle_critical_error(error, "test context", should_exit=True, exit_code=42)

        mock_exit.assert_called_once_with(42)
