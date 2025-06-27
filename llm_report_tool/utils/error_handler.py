"""
Error handling utilities for the LLM report tool.
"""
import functools
import logging
import time
import traceback
from typing import Any, Callable, Optional, Type, Union

from ..exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    reraise_as: Optional[Type[Exception]] = None,
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Factor by which delay increases each retry
        max_delay: Maximum delay between retries
        exceptions: Exception types to catch and retry
        on_retry: Callback function called on each retry attempt
        reraise_as: Exception type to reraise as after all retries exhausted

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # All retries exhausted
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries. "
                            f"Last error: {str(e)}"
                        )
                        if reraise_as:
                            raise reraise_as(f"Failed after {max_retries} retries: {str(e)}") from e
                        else:
                            raise RetryExhaustedError(
                                f"Failed after {max_retries} retries: {str(e)}"
                            ) from e

                    # Log retry attempt
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}: {str(e)}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)

                    # Wait before retrying
                    time.sleep(delay)

                    # Increase delay for next retry
                    delay = min(delay * backoff_factor, max_delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    **kwargs,
) -> Any:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        default_return: Value to return if function fails
        log_errors: Whether to log errors
        reraise: Whether to reraise the exception after logging
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return if function fails
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(
                f"Error executing {func.__name__}: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            )

        if reraise:
            raise

        return default_return


def handle_critical_error(
    error: Exception, context: str, should_exit: bool = False, exit_code: int = 1
) -> None:
    """
    Handle critical errors that may require application shutdown.

    Args:
        error: The exception that occurred
        context: Context description of where the error occurred
        should_exit: Whether to exit the application
        exit_code: Exit code to use if exiting
    """
    logger.critical(
        f"Critical error in {context}: {str(error)}\n" f"Traceback: {traceback.format_exc()}"
    )

    if should_exit:
        import sys

        sys.exit(exit_code)


class ErrorContext:
    """Context manager for handling errors in a specific context."""

    def __init__(
        self,
        context_name: str,
        log_level: int = logging.ERROR,
        reraise: bool = True,
        default_return: Any = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        self.context_name = context_name
        self.log_level = log_level
        self.reraise = reraise
        self.default_return = default_return
        self.on_error = on_error
        self.error_occurred = False
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_occurred = True
            self.exception = exc_val

            logger.log(
                self.log_level,
                f"Error in {self.context_name}: {str(exc_val)}\n"
                f"Traceback: {traceback.format_exc()}",
            )

            if self.on_error:
                self.on_error(exc_val)

            if not self.reraise:
                return True  # Suppress the exception

        return False
