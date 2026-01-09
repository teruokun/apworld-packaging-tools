# SPDX-License-Identifier: MIT
"""Rate limiting middleware."""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class RateLimitState:
    """Track rate limit state for a client."""

    tokens: float
    last_update: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting middleware.

    Implements rate limiting with burst support using the token bucket algorithm.
    Adds standard rate limit headers to all responses.
    """

    def __init__(
        self,
        app: Callable,
        requests_per_minute: int = 100,
        burst_size: int = 20,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self._buckets: dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(tokens=burst_size, last_update=time.time())
        )

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use X-Forwarded-For if behind proxy, otherwise use client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(self, client_id: str) -> tuple[bool, int, int, int]:
        """Check if request is within rate limit.

        Returns:
            Tuple of (allowed, limit, remaining, reset_seconds)
        """
        now = time.time()
        state = self._buckets[client_id]

        # Refill tokens based on time elapsed
        elapsed = now - state.last_update
        state.tokens = min(self.burst_size, state.tokens + elapsed * self.refill_rate)
        state.last_update = now

        # Check if we have tokens available
        if state.tokens >= 1:
            state.tokens -= 1
            remaining = int(state.tokens)
            return True, self.requests_per_minute, remaining, 60

        # Calculate time until next token
        reset_seconds = int((1 - state.tokens) / self.refill_rate) + 1
        return False, self.requests_per_minute, 0, reset_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_id = self._get_client_id(request)
        allowed, limit, remaining, reset = self._check_rate_limit(client_id)

        # Add rate limit headers to all responses
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset),
        }

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded. Retry after {reset} seconds",
                    }
                },
                headers={**headers, "Retry-After": str(reset)},
            )

        response = await call_next(request)

        # Add headers to successful response
        for key, value in headers.items():
            response.headers[key] = value

        return response
