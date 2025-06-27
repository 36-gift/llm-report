"""
Advanced rate limiting utilities for API calls.
"""
import asyncio
import logging
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock, RLock
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    backoff_factor: float = 2.0
    max_delay: float = 300.0  # 5 minutes
    jitter: bool = True


class TokenBucket:
    """Token bucket implementation for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self.lock = Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate time until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Time in seconds until tokens are available
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class SlidingWindowRateLimiter:
    """Sliding window rate limiter implementation."""

    def __init__(self, window_size: int, max_requests: int):
        """
        Initialize sliding window rate limiter.

        Args:
            window_size: Window size in seconds
            max_requests: Maximum requests per window
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        with self.lock:
            now = time.time()

            # Remove old requests outside the window
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()

            # Check if we can make a new request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    def time_until_available(self) -> float:
        """Calculate time until next request is allowed."""
        with self.lock:
            now = time.time()

            # Remove old requests
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()

            if len(self.requests) < self.max_requests:
                return 0.0

            # Time until oldest request falls out of window
            return self.requests[0] + self.window_size - now


class APIRateLimiter:
    """Advanced API rate limiter with multiple strategies and endpoints."""

    def __init__(self):
        """Initialize the rate limiter."""
        self.endpoint_configs: Dict[str, RateLimitConfig] = {}
        self.endpoint_limiters: Dict[str, Union[TokenBucket, SlidingWindowRateLimiter]] = {}
        self.request_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_requests: Dict[str, float] = {}
        self.lock = RLock()

        # Track API health
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.last_error_time: Dict[str, float] = {}

    def configure_endpoint(self, endpoint: str, config: RateLimitConfig):
        """
        Configure rate limiting for an endpoint.

        Args:
            endpoint: API endpoint identifier
            config: Rate limit configuration
        """
        with self.lock:
            self.endpoint_configs[endpoint] = config

            if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                # Convert requests per minute to refill rate
                refill_rate = config.requests_per_minute / 60.0
                self.endpoint_limiters[endpoint] = TokenBucket(
                    capacity=config.burst_size, refill_rate=refill_rate
                )
            elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                self.endpoint_limiters[endpoint] = SlidingWindowRateLimiter(
                    window_size=60, max_requests=config.requests_per_minute  # 1 minute window
                )

    def can_make_request(self, endpoint: str) -> tuple[bool, float]:
        """
        Check if a request can be made to an endpoint.

        Args:
            endpoint: API endpoint identifier

        Returns:
            Tuple of (can_make_request, wait_time_seconds)
        """
        if endpoint not in self.endpoint_configs:
            # No rate limiting configured, allow request
            return True, 0.0

        config = self.endpoint_configs[endpoint]
        limiter = self.endpoint_limiters[endpoint]

        # Check for circuit breaker conditions
        if self._is_circuit_open(endpoint):
            wait_time = self._get_circuit_breaker_wait_time(endpoint)
            return False, wait_time

        if isinstance(limiter, TokenBucket):
            if limiter.consume():
                return True, 0.0
            else:
                wait_time = limiter.time_until_available()
                return False, wait_time

        elif isinstance(limiter, SlidingWindowRateLimiter):
            if limiter.is_allowed():
                return True, 0.0
            else:
                wait_time = limiter.time_until_available()
                return False, wait_time

        return True, 0.0

    def record_request_result(self, endpoint: str, success: bool, response_time: float = 0.0):
        """
        Record the result of an API request.

        Args:
            endpoint: API endpoint identifier
            success: Whether the request was successful
            response_time: Response time in seconds
        """
        with self.lock:
            if success:
                self.success_counts[endpoint] += 1
                # Reset error count on success
                if endpoint in self.error_counts:
                    self.error_counts[endpoint] = max(0, self.error_counts[endpoint] - 1)
            else:
                self.error_counts[endpoint] += 1
                self.last_error_time[endpoint] = time.time()

    def _is_circuit_open(self, endpoint: str) -> bool:
        """Check if circuit breaker is open for an endpoint."""
        error_count = self.error_counts.get(endpoint, 0)
        success_count = self.success_counts.get(endpoint, 0)

        # Open circuit if error rate is too high
        total_requests = error_count + success_count
        if total_requests >= 10:  # Minimum sample size
            error_rate = error_count / total_requests
            if error_rate > 0.5:  # 50% error rate
                return True

        # Open circuit if too many consecutive errors
        if error_count >= 5:
            return True

        return False

    def _get_circuit_breaker_wait_time(self, endpoint: str) -> float:
        """Get wait time for circuit breaker."""
        last_error = self.last_error_time.get(endpoint, 0)
        if last_error == 0:
            return 0.0

        # Exponential backoff starting at 30 seconds
        elapsed = time.time() - last_error
        wait_time = min(
            30 * (2 ** min(self.error_counts.get(endpoint, 0), 5)), 300
        )  # Max 5 minutes

        return max(0, wait_time - elapsed)

    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get statistics for an endpoint."""
        return {
            "success_count": self.success_counts.get(endpoint, 0),
            "error_count": self.error_counts.get(endpoint, 0),
            "is_circuit_open": self._is_circuit_open(endpoint),
            "wait_time": self._get_circuit_breaker_wait_time(endpoint),
        }

    def reset_endpoint_stats(self, endpoint: str):
        """Reset statistics for an endpoint."""
        with self.lock:
            self.success_counts.pop(endpoint, None)
            self.error_counts.pop(endpoint, None)
            self.last_error_time.pop(endpoint, None)


# Global rate limiter instance
rate_limiter = APIRateLimiter()


def rate_limited(
    endpoint: str,
    max_retries: int = 10,
    backoff_factor: float = 2.0,
    max_delay: float = 300.0,
    jitter: bool = True,
):
    """
    Decorator for rate-limited API calls with enhanced error handling.

    Args:
        endpoint: API endpoint identifier
        max_retries: Maximum number of retries
        backoff_factor: Exponential backoff factor
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to delays
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                # Check rate limits
                can_proceed, wait_time = rate_limiter.can_make_request(endpoint)

                if not can_proceed:
                    if wait_time > max_delay:
                        logger.error(
                            f"Rate limit wait time ({wait_time:.1f}s) exceeds maximum ({max_delay}s)"
                        )
                        raise Exception(f"Rate limit exceeded for {endpoint}")

                    # Add jitter to wait time to prevent thundering herd
                    if jitter and wait_time > 0:
                        jitter_factor = random.uniform(0.1, 0.3)  # 10-30% jitter
                        wait_time *= 1 + jitter_factor

                    logger.info(f"Rate limited for {endpoint}, waiting {wait_time:.1f} seconds")
                    time.sleep(wait_time)
                    continue

                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    response_time = time.time() - start_time

                    # Record successful request
                    rate_limiter.record_request_result(endpoint, True, response_time)

                    # Log performance metrics for monitoring
                    if response_time > 30.0:  # Log slow requests
                        logger.warning(f"Slow API response for {endpoint}: {response_time:.2f}s")
                    elif response_time > 10.0:
                        logger.info(f"API response time for {endpoint}: {response_time:.2f}s")

                    return result

                except Exception as e:
                    last_exception = e
                    response_time = time.time() - start_time
                    rate_limiter.record_request_result(endpoint, False, response_time)

                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {endpoint}: {str(e)}"
                        )
                        raise

                    # Calculate backoff delay with jitter
                    base_delay = min(backoff_factor**attempt, max_delay)

                    if jitter:
                        # Add jitter: ±25% of base delay
                        jitter_range = base_delay * 0.25
                        delay = base_delay + random.uniform(-jitter_range, jitter_range)
                        delay = max(1.0, delay)  # Minimum 1 second delay
                    else:
                        delay = base_delay

                    logger.warning(
                        f"API call failed for {endpoint} (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f} seconds: {str(e)}"
                    )
                    time.sleep(delay)

            # This should never be reached due to the raise in the exception handler,
            # but included for completeness
            if last_exception:
                raise last_exception
            else:
                raise Exception(f"Max retries exceeded for {endpoint}")

        return wrapper

    return decorator


def configure_siliconflow_rate_limits():
    """Configure rate limits for SiliconFlow API endpoints."""
    # Conservative rate limits for SiliconFlow API
    # SiliconFlow typically allows higher limits, but we use conservative values for stability
    config = RateLimitConfig(
        requests_per_minute=40,  # Conservative limit for chat completions
        requests_per_hour=1200,  # 40 RPM * 60 minutes = 2400, using 50% for safety
        burst_size=8,  # Allow small bursts
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        backoff_factor=2.0,
        max_delay=300.0,
        jitter=True,  # Add jitter to prevent thundering herd
    )

    # Different endpoints may have different limits
    summarization_config = RateLimitConfig(
        requests_per_minute=30,  # Slightly lower for summarization (typically more expensive)
        requests_per_hour=900,
        burst_size=6,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        backoff_factor=2.0,
        max_delay=300.0,
        jitter=True,
    )

    classification_config = RateLimitConfig(
        requests_per_minute=50,  # Higher for classification (typically cheaper)
        requests_per_hour=1500,
        burst_size=10,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        backoff_factor=2.0,
        max_delay=300.0,
        jitter=True,
    )

    rate_limiter.configure_endpoint("siliconflow_chat", config)
    rate_limiter.configure_endpoint("siliconflow_summary", summarization_config)
    rate_limiter.configure_endpoint("siliconflow_classify", classification_config)

    # Also maintain backward compatibility with DeepSeek naming
    rate_limiter.configure_endpoint("deepseek_chat", config)
    rate_limiter.configure_endpoint("deepseek_summary", summarization_config)
    rate_limiter.configure_endpoint("deepseek_classify", classification_config)

    logger.info("Configured SiliconFlow API rate limits with jitter and burst handling")


def configure_reddit_rate_limits():
    """Configure rate limits for Reddit API endpoints."""
    reddit_config = RateLimitConfig(
        requests_per_minute=60,  # Reddit is generally more permissive
        requests_per_hour=3000,
        burst_size=15,
        strategy=RateLimitStrategy.SLIDING_WINDOW,  # Better for web scraping
        backoff_factor=1.5,  # Gentler backoff for web scraping
        max_delay=180.0,  # 3 minutes max delay
        jitter=True,
    )

    rate_limiter.configure_endpoint("reddit_api", reddit_config)
    rate_limiter.configure_endpoint("reddit_scrape", reddit_config)

    logger.info("Configured Reddit API rate limits")


# Initialize default rate limits
configure_siliconflow_rate_limits()
configure_reddit_rate_limits()
