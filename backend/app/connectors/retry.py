"""Compatibility wrapper around CivicCore live-sync retry primitives."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import httpx
from civiccore.connectors import (
    SyncRetryExhausted,
    SyncRetryPolicy,
    compute_retry_delay,
    with_http_retry,
)

_RETRY_POLICY = SyncRetryPolicy()
_REQUEST_TIMEOUT = 30.0  # per-request timeout in seconds

RetryExhausted = SyncRetryExhausted


def _compute_delay(attempt: int, retry_after: float | None = None) -> float | None:
    """Return the shared CivicCore delay for this retry attempt."""

    return compute_retry_delay(
        attempt,
        retry_after_seconds=retry_after,
        policy=_RETRY_POLICY,
    )


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

    return await with_http_retry(
        action,
        policy=_RETRY_POLICY,
        bypass_retry=bypass_retry,
        sleep=asyncio.sleep,
    )
