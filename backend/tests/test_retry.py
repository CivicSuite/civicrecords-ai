import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.connectors.retry import RetryExhausted, _compute_delay, with_retry


@pytest.mark.asyncio
async def test_success_on_first_attempt():
    action = AsyncMock(return_value=httpx.Response(200))
    result = await with_retry(action)
    assert result.status_code == 200
    action.assert_called_once()


@pytest.mark.asyncio
async def test_retry_on_429_then_success():
    responses = [httpx.Response(429), httpx.Response(200)]
    idx = 0

    async def action():
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r

    with patch("app.connectors.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(action)
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_retry_exhausted_on_all_429():
    action = AsyncMock(return_value=httpx.Response(429))
    with patch("app.connectors.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RetryExhausted):
            await with_retry(action)


@pytest.mark.asyncio
async def test_retry_after_header_respected():
    responses = [
        httpx.Response(429, headers={"Retry-After": "5"}),
        httpx.Response(200),
    ]
    idx = 0

    async def action():
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r

    with patch("app.connectors.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await with_retry(action)
    sleep_duration = mock_sleep.call_args[0][0]
    assert 4.0 <= sleep_duration <= 6.5  # 5s ± 20% jitter + tolerance


@pytest.mark.asyncio
async def test_retry_after_honored_up_to_600s_cap():
    """Retry-After values ≤ 600 are honored (D10 spec); > 600 are capped to 600.
    This replaces the old ceiling=30s behavior which was incorrect per spec."""
    # Retry-After: 35 → honor 35s, retry, succeed on second call
    call_count = 0
    async def action():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "35"})
        return httpx.Response(200)

    with patch("app.connectors.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await with_retry(action)
    assert result.status_code == 200
    mock_sleep.assert_called_once_with(35.0)

    # Retry-After: 9999 → capped to 600s
    calls_9999 = 0
    async def action_9999():
        nonlocal calls_9999
        calls_9999 += 1
        if calls_9999 == 1:
            return httpx.Response(429, headers={"Retry-After": "9999"})
        return httpx.Response(200)

    with patch("app.connectors.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await with_retry(action_9999)
    assert result.status_code == 200
    mock_sleep.assert_called_once_with(600.0)


@pytest.mark.asyncio
async def test_bypass_retry_executes_once():
    action = AsyncMock(return_value=httpx.Response(200))
    result = await with_retry(action, bypass_retry=True)
    assert result.status_code == 200
    action.assert_called_once()


@pytest.mark.asyncio
async def test_bypass_retry_no_retry_on_429():
    """bypass_retry=True must NOT retry even on 429."""
    action = AsyncMock(return_value=httpx.Response(429))
    result = await with_retry(action, bypass_retry=True)
    assert result.status_code == 429
    action.assert_called_once()


def test_compute_delay_exponential():
    d0 = _compute_delay(0)
    d1 = _compute_delay(1)
    assert d0 is not None and d1 is not None
    assert d1 > d0  # exponential growth
