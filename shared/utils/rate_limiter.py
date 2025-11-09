"""
Rate Limiter - Prevents exceeding rate limits
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta
from typing import Optional


class RateLimiter:
    """
    Async-safe rate limiter using sliding window algorithm

    Example:
        limiter = RateLimiter(max_requests=30, time_window=60)  # 30 req/min

        async def scrape():
            await limiter.acquire()
            # Make request here
    """

    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize RateLimiter

        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Will wait if rate limit is reached.
        """
        async with self._lock:
            now = datetime.utcnow()

            # Remove requests outside the time window
            while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
                self.requests.popleft()

            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                # Calculate how long to wait
                oldest_request = self.requests[0]
                wait_until = oldest_request + timedelta(seconds=self.time_window)
                wait_seconds = (wait_until - now).total_seconds()

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    # After waiting, remove old requests again
                    now = datetime.utcnow()
                    while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
                        self.requests.popleft()

            # Record this request
            self.requests.append(datetime.utcnow())

    def reset(self) -> None:
        """Clear all request history"""
        self.requests.clear()

    @property
    def current_usage(self) -> int:
        """Get current number of requests in the window"""
        now = datetime.utcnow()
        # Count requests within time window
        return sum(
            1 for req_time in self.requests
            if req_time >= now - timedelta(seconds=self.time_window)
        )

    @property
    def available_requests(self) -> int:
        """Get number of available requests in current window"""
        return max(0, self.max_requests - self.current_usage)


class MultiRateLimiter:
    """
    Manage multiple rate limiters for different resources

    Example:
        limiters = MultiRateLimiter({
            'api': RateLimiter(100, 60),      # 100 req/min for API
            'scraping': RateLimiter(30, 60)   # 30 req/min for scraping
        })

        await limiters.acquire('api')
    """

    def __init__(self, limiters: dict[str, RateLimiter]):
        """
        Initialize MultiRateLimiter

        Args:
            limiters: Dictionary of name -> RateLimiter
        """
        self.limiters = limiters

    async def acquire(self, limiter_name: str) -> None:
        """Acquire from a specific limiter"""
        if limiter_name in self.limiters:
            await self.limiters[limiter_name].acquire()

    def add_limiter(self, name: str, limiter: RateLimiter) -> None:
        """Add a new rate limiter"""
        self.limiters[name] = limiter

    def reset_all(self) -> None:
        """Reset all limiters"""
        for limiter in self.limiters.values():
            limiter.reset()

    def get_stats(self) -> dict[str, dict]:
        """Get statistics for all limiters"""
        return {
            name: {
                'current_usage': limiter.current_usage,
                'available_requests': limiter.available_requests,
                'max_requests': limiter.max_requests,
                'time_window': limiter.time_window
            }
            for name, limiter in self.limiters.items()
        }
