"""
Error Handler - Retry logic with exponential backoff
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Optional, Type, Tuple

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retrying async functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback function called on each retry

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1)
        async def fetch_data(url):
            # Your code here
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0

            while retries <= max_retries:
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    retries += 1

                    if retries > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                            f"Last error: {str(e)}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (retries - 1)),
                        max_delay
                    )

                    logger.warning(
                        f"Error in {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f}s... (Attempt {retries}/{max_retries})"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            await on_retry(retries, delay, e)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")

                    await asyncio.sleep(delay)

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures

    States:
        - CLOSED: Normal operation, requests go through
        - OPEN: Too many failures, requests are blocked
        - HALF_OPEN: Testing if service recovered

    Example:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        async def call_api():
            if not breaker.can_execute():
                raise Exception("Circuit breaker is OPEN")

            try:
                result = await api_call()
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize CircuitBreaker

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting to close circuit
            expected_exception: Exception type that counts as failure
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if timeout has passed
            if self.last_failure_time:
                import time
                if time.time() - self.last_failure_time >= self.timeout:
                    self.state = "HALF_OPEN"
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
            return False

        if self.state == "HALF_OPEN":
            return True

        return False

    def record_success(self) -> None:
        """Record successful request"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker CLOSED after successful request")

        self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed request"""
        import time

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning("Circuit breaker OPEN (failed during HALF_OPEN)")

        elif self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )

    def reset(self) -> None:
        """Manually reset circuit breaker"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        logger.info("Circuit breaker manually reset to CLOSED")


# Common error handling utilities

async def handle_network_errors(func: Callable, *args, **kwargs):
    """
    Handle common network errors with appropriate retry logic
    """
    @retry_with_backoff(
        max_retries=4,
        base_delay=2.0,
        exceptions=(ConnectionError, TimeoutError, OSError)
    )
    async def wrapped():
        return await func(*args, **kwargs)

    return await wrapped()


async def handle_rate_limit_errors(func: Callable, *args, **kwargs):
    """
    Handle rate limit errors (HTTP 429) with longer backoff
    """
    @retry_with_backoff(
        max_retries=3,
        base_delay=15.0,
        max_delay=300.0
    )
    async def wrapped():
        return await func(*args, **kwargs)

    return await wrapped()
