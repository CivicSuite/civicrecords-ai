"""Cron expression utilities: validation and next-run computation."""
from datetime import datetime, timezone

from croniter import croniter, CroniterBadCronError

UTC = timezone.utc


def min_interval_minutes(expr: str) -> int:
    """Compute minimum interval between firings over a rolling 7-day window.

    Samples 2016 consecutive tick pairs (7 days x 288 5-min ticks/day) to detect
    adversarial expressions like '*/1 0 * * *' that fire every minute in one hour.

    Returns minimum gap in whole minutes.
    Raises ValueError for unparseable expressions.
    """
    try:
        it = croniter(expr, datetime.now(UTC))
    except (CroniterBadCronError, ValueError) as e:
        raise ValueError(f"Invalid cron expression '{expr}': {e}") from e

    prev = it.get_next(datetime)
    min_gap = float("inf")
    for _ in range(2016):
        nxt = it.get_next(datetime)
        gap = (nxt - prev).total_seconds() / 60
        if gap < min_gap:
            min_gap = gap
        prev = nxt
    return int(min_gap)


def validate_cron_expression(expr: str) -> None:
    """Validate a cron expression. Raises ValueError with a user-facing message if invalid.

    Checks:
    1. Expression is parseable by croniter.
    2. Minimum interval across 7-day window is >= 5 minutes.
    """
    try:
        croniter(expr, datetime.now(UTC))
    except (CroniterBadCronError, ValueError):
        raise ValueError(f"Invalid cron expression: '{expr}'. Use standard 5-field cron syntax.")

    gap = min_interval_minutes(expr)
    if gap < 5:
        raise ValueError(
            f"Schedule fires more frequently than every 5 minutes "
            f"(minimum gap detected: {gap} min). Minimum allowed interval is 5 minutes."
        )


def compute_next_sync_at(sync_schedule: str, last_sync_at: datetime | None) -> datetime | None:
    """Compute the next scheduled run time from the last sync anchor.

    Returns None if sync_schedule is empty/None.
    """
    if not sync_schedule:
        return None
    anchor = last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
    it = croniter(sync_schedule, anchor)
    return it.get_next(datetime)
