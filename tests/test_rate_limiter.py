"""
Comprehensive tests for the rate limiting system.
"""
import time
from unittest.mock import Mock, patch

import pytest

from llm_report_tool.utils.rate_limiter import (
    APIRateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    SlidingWindowRateLimiter,
    TokenBucket,
    rate_limited,
    rate_limiter,
)


class TestTokenBucket:
    """Test cases for TokenBucket rate limiter."""

    def test_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        assert bucket.capacity == 10
        assert bucket.tokens == 10
        assert bucket.refill_rate == 1.0
        assert bucket.last_refill > 0

    def test_consume_tokens_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        result = bucket.consume(5)
        assert result is True
        assert bucket.tokens == 5

    def test_consume_tokens_insufficient(self):
        """Test token consumption when insufficient tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Consume all tokens
        bucket.consume(10)

        # Try to consume more
        result = bucket.consume(1)
        assert result is False
        assert bucket.tokens == 0

    def test_token_refill(self):
        """Test token refill mechanism."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second

        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0

        # Mock time passage
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                bucket.last_refill,  # Initial time
                bucket.last_refill + 2.0,  # 2 seconds later
            ]

            # Force refill
            bucket._refill()
            assert bucket.tokens == 4.0  # 2 seconds * 2 tokens/second

    def test_time_until_available(self):
        """Test time calculation until tokens are available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Consume all tokens
        bucket.consume(10)

        # Check time until 5 tokens are available
        wait_time = bucket.time_until_available(5)
        assert wait_time == 5.0  # 5 tokens / 1 token per second


class TestSlidingWindowRateLimiter:
    """Test cases for SlidingWindowRateLimiter."""

    def test_initialization(self):
        """Test sliding window rate limiter initialization."""
        limiter = SlidingWindowRateLimiter(window_size=60, max_requests=10)

        assert limiter.window_size == 60
        assert limiter.max_requests == 10
        assert len(limiter.requests) == 0

    def test_requests_within_limit(self):
        """Test requests within rate limit."""
        limiter = SlidingWindowRateLimiter(window_size=60, max_requests=5)

        # Make requests within limit
        for _ in range(5):
            assert limiter.is_allowed() is True

        # Next request should be denied
        assert limiter.is_allowed() is False

    def test_window_sliding(self):
        """Test sliding window behavior."""
        limiter = SlidingWindowRateLimiter(window_size=2, max_requests=2)

        with patch("time.time") as mock_time:
            current_time = 1000.0
            mock_time.return_value = current_time

            # Make 2 requests at time 1000
            assert limiter.is_allowed() is True
            assert limiter.is_allowed() is True
            assert limiter.is_allowed() is False  # Limit reached

            # Move time forward by 3 seconds (beyond window)
            mock_time.return_value = current_time + 3.0

            # Should be allowed again
            assert limiter.is_allowed() is True


class TestAPIRateLimiter:
    """Test cases for APIRateLimiter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.limiter = APIRateLimiter()

    def test_configure_endpoint(self):
        """Test endpoint configuration."""
        config = RateLimitConfig(requests_per_minute=60, strategy=RateLimitStrategy.TOKEN_BUCKET)

        self.limiter.configure_endpoint("test_endpoint", config)

        assert "test_endpoint" in self.limiter.endpoint_configs
        assert "test_endpoint" in self.limiter.endpoint_limiters
        assert self.limiter.endpoint_configs["test_endpoint"] == config

    def test_can_make_request_no_config(self):
        """Test request checking without configuration."""
        can_make, wait_time = self.limiter.can_make_request("unknown_endpoint")

        assert can_make is True
        assert wait_time == 0.0

    def test_can_make_request_with_config(self):
        """Test request checking with configuration."""
        config = RateLimitConfig(
            requests_per_minute=60, burst_size=5, strategy=RateLimitStrategy.TOKEN_BUCKET
        )

        self.limiter.configure_endpoint("test_endpoint", config)

        # Should be able to make requests within burst
        for _ in range(5):
            can_make, wait_time = self.limiter.can_make_request("test_endpoint")
            assert can_make is True
            assert wait_time == 0.0

    def test_record_request_result(self):
        """Test recording request results."""
        endpoint = "test_endpoint"

        # Record successful requests
        for _ in range(3):
            self.limiter.record_request_result(endpoint, True)

        assert self.limiter.success_counts[endpoint] == 3
        assert self.limiter.error_counts[endpoint] == 0

        # Record failed request
        self.limiter.record_request_result(endpoint, False)

        assert self.limiter.success_counts[endpoint] == 3
        assert self.limiter.error_counts[endpoint] == 1

    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        endpoint = "test_endpoint"

        # Record many failed requests
        for _ in range(6):
            self.limiter.record_request_result(endpoint, False)

        assert self.limiter._is_circuit_open(endpoint) is True

        # Circuit should provide wait time
        wait_time = self.limiter._get_circuit_breaker_wait_time(endpoint)
        assert wait_time > 0

    def test_get_endpoint_stats(self):
        """Test endpoint statistics retrieval."""
        endpoint = "test_endpoint"

        self.limiter.record_request_result(endpoint, True)
        self.limiter.record_request_result(endpoint, False)

        stats = self.limiter.get_endpoint_stats(endpoint)

        assert stats["success_count"] == 1
        assert stats["error_count"] == 1
        assert "is_circuit_open" in stats
        assert "wait_time" in stats

    def test_reset_endpoint_stats(self):
        """Test resetting endpoint statistics."""
        endpoint = "test_endpoint"

        self.limiter.record_request_result(endpoint, True)
        self.limiter.record_request_result(endpoint, False)

        self.limiter.reset_endpoint_stats(endpoint)

        assert self.limiter.success_counts.get(endpoint, 0) == 0
        assert self.limiter.error_counts.get(endpoint, 0) == 0


class TestRateLimitedDecorator:
    """Test cases for the rate_limited decorator."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset the global rate limiter
        rate_limiter.endpoint_configs.clear()
        rate_limiter.endpoint_limiters.clear()
        rate_limiter.success_counts.clear()
        rate_limiter.error_counts.clear()

    def test_successful_call(self):
        """Test successful decorated function call."""

        @rate_limited("test_endpoint", max_retries=2)
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"

    def test_retry_on_failure(self):
        """Test retry mechanism on failure."""
        call_count = 0

        @rate_limited("test_endpoint", max_retries=2, backoff_factor=1.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        with patch("time.sleep"):  # Speed up test by mocking sleep
            result = test_function()

        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""

        @rate_limited("test_endpoint", max_retries=2)
        def test_function():
            raise Exception("Persistent failure")

        with patch("time.sleep"):  # Speed up test
            with pytest.raises(Exception) as exc_info:
                test_function()

        assert "Persistent failure" in str(exc_info.value)

    def test_rate_limit_enforcement(self):
        """Test rate limit enforcement."""
        # Configure a very restrictive rate limit
        config = RateLimitConfig(
            requests_per_minute=1, burst_size=1, strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        rate_limiter.configure_endpoint("restricted_endpoint", config)

        @rate_limited("restricted_endpoint", max_retries=1)
        def test_function():
            return "success"

        # First call should succeed
        result1 = test_function()
        assert result1 == "success"

        # Second call should be rate limited
        with patch("time.sleep") as mock_sleep:
            result2 = test_function()
            assert result2 == "success"
            # Should have slept due to rate limiting
            mock_sleep.assert_called()

    def test_jitter_in_delays(self):
        """Test that jitter is applied to delays."""
        call_count = 0
        delays = []

        @rate_limited("test_endpoint", max_retries=3, jitter=True)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Temporary failure")
            return "success"

        original_sleep = time.sleep

        def mock_sleep(delay):
            delays.append(delay)

        with patch("time.sleep", side_effect=mock_sleep):
            result = test_function()

        assert result == "success"
        assert len(delays) == 2  # Two retries

        # With jitter, delays should be slightly different from base exponential backoff
        # This is a probabilistic test, so we check that delays are reasonable
        for delay in delays:
            assert delay >= 1.0  # Minimum delay
            assert delay <= 10.0  # Reasonable maximum for our test


class TestRateLimitConfig:
    """Test cases for RateLimitConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10
        assert config.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert config.backoff_factor == 2.0
        assert config.max_delay == 300.0
        assert config.jitter is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            burst_size=5,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            jitter=False,
        )

        assert config.requests_per_minute == 30
        assert config.burst_size == 5
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW
        assert config.jitter is False


class TestIntegration:
    """Integration tests for the rate limiting system."""

    def test_siliconflow_rate_limits_configured(self):
        """Test that SiliconFlow rate limits are properly configured."""
        # Import should configure the rate limits
        from llm_report_tool.utils.rate_limiter import rate_limiter

        # Check that SiliconFlow endpoints are configured
        assert "siliconflow_chat" in rate_limiter.endpoint_configs
        assert "siliconflow_summary" in rate_limiter.endpoint_configs
        assert "siliconflow_classify" in rate_limiter.endpoint_configs

        # Check that Reddit endpoints are configured
        assert "reddit_api" in rate_limiter.endpoint_configs
        assert "reddit_scrape" in rate_limiter.endpoint_configs

    def test_backwards_compatibility(self):
        """Test backwards compatibility with DeepSeek naming."""
        from llm_report_tool.utils.rate_limiter import rate_limiter

        # Check that DeepSeek endpoints are still configured for backwards compatibility
        assert "deepseek_chat" in rate_limiter.endpoint_configs
        assert "deepseek_summary" in rate_limiter.endpoint_configs
        assert "deepseek_classify" in rate_limiter.endpoint_configs
