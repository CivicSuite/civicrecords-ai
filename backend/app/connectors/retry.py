import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

_MAX_ATTEMPTS = 3
_BASE_DELAY = 1.0      # seconds
_JITTER_FACTOR = 0.2   # ±20%
_CEILING = 30.0        # seconds — if delay would exceed this, raise immediately
_REQUEST_TIMEOUT = 30.0  # per-request timeout in seconds


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""


def _compute_delay(attempt: int, retry_after: float | None = None) -> float | None:
    """Return sleep duration for this attempt, or None to raise immediately (ceiling exceeded)."""
    if retry_after is not None:
        if retry_after > _CEILING:
            return None  # ceiling exceeded — fail immediately
        jitter = retry_after * _JITTER_FACTOR * (2 * random.random() - 1)
        return retry_after + jitter
    delay = _BASE_DELAY * (2 ** attempt)
    jitter = delay * _JITTER_FACTOR * (2 * random.random() - 1)
    delay = delay + jitter
    if delay > _CEILING:
        return None  # ceiling exceeded
    return delay


async def with_retry(
    action: Callable[[], Awaitable[httpx.Response]],
    *,
    bypass_retry: bool = False,
) -> httpx.Response:
    """
    Execute an async HTTP action with retry on 429/5xx.

    Args:
        action: Async callable returning httpx.Response.
        bypass_retry: When True, execute once without any retry (test-connection path).
    """
    if bypass_retry:
        return await action()

    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await action()
            if response.status_code == 429:
                retry_after_raw = response.headers.get("Retry-After")
                try:
                    retry_after: float | None = float(retry_after_raw) if retry_after_raw else None
                except (ValueError, TypeError):
                    retry_after = None
                if retry_after is not None:
                    # Honor Retry-After header, cap at 600s per D10 spec
                    wait = min(retry_after, 600.0)
                    if attempt == _MAX_ATTEMPTS - 1:
                        raise RetryExhausted(
                            f"Rate limited after {attempt + 1} attempt(s); "
                            f"Retry-After={retry_after}"
                        )
                    logger.warning(
                        "Rate limited (429), waiting %.1fs (Retry-After: %s, attempt %d/%d)",
                        wait, retry_after_raw, attempt + 1, _MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(wait)
                else:
                    # No valid Retry-After — fall back to exponential backoff
                    delay = _compute_delay(attempt)
                    if delay is None or attempt == _MAX_ATTEMPTS - 1:
                        raise RetryExhausted(
                            f"Rate limited after {attempt + 1} attempt(s); "
                            f"no valid Retry-After header"
                        )
                    logger.warning(
                        "Rate limited (429, no Retry-After), retrying in %.1fs (attempt %d/%d)",
                        delay, attempt + 1, _MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                continue
            if response.status_code >= 500:
                delay = _compute_delay(attempt)
                if delay is None or attempt == _MAX_ATTEMPTS - 1:
                    raise RetryExhausted(
                        f"Server error {response.status_code} after {attempt + 1} attempt(s)"
                    )
                logger.warning(
                    "Server error %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code, delay, attempt + 1, _MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue
            return response
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            delay = _compute_delay(attempt)
            if delay is None or attempt == _MAX_ATTEMPTS - 1:
                raise RetryExhausted(
                    f"Connection error after {attempt + 1} attempt(s): {exc}"
                ) from exc
            logger.warning(
                "Connection error, retrying in %.1fs: %s", delay, exc
            )
            await asyncio.sleep(delay)

    raise RetryExhausted(f"Exhausted {_MAX_ATTEMPTS} attempts") from last_exc
