import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import get_settings

settings = get_settings()


class InMemoryRateLimiter:
    """Small per-process limiter for sensitive unauthenticated endpoints.

    Use a shared limiter (Redis/API gateway) when the service runs on more
    than one process or host.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            timestamps = self.requests[key]
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )
            timestamps.append(now)

    def clear(self, key: str) -> None:
        """Clear failed-attempt history after a successful authentication."""
        with self.lock:
            self.requests.pop(key, None)


login_limiter = InMemoryRateLimiter(
    settings.login_rate_limit,
    settings.login_rate_window_seconds,
)
qr_limiter = InMemoryRateLimiter(
    settings.qr_rate_limit,
    settings.qr_rate_window_seconds,
)


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_qr_verification(request: Request) -> None:
    qr_limiter.check(client_address(request))
