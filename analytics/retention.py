from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import AnalyticsEvent, EventType


def _get_cohort_day0(db: Session) -> dict:
    """
    Returns {discord_id: day0_datetime}, where day0 is the earliest
    role_verified event per user -- the cohort start date.
    """
    rows = (
        db.query(AnalyticsEvent.discord_id, func.min(AnalyticsEvent.created_at))
        .filter(AnalyticsEvent.event_type == EventType.ROLE_VERIFIED)
        .group_by(AnalyticsEvent.discord_id)
        .all()
    )
    return {discord_id: day0 for discord_id, day0 in rows}


def _get_message_timestamps(db: Session) -> dict:
    """Returns {discord_id: [message_sent timestamps]}."""
    rows = (
        db.query(AnalyticsEvent.discord_id, AnalyticsEvent.created_at)
        .filter(AnalyticsEvent.event_type == EventType.MESSAGE_SENT)
        .all()
    )
    result = defaultdict(list)
    for discord_id, created_at in rows:
        result[discord_id].append(created_at)
    return result


def _compute_window(
    cohort: dict, messages: dict, window_days: int, now: datetime
) -> tuple[Optional[float], int, int]:
    """
    For a given window (1/7/30 days), only counts users whose cohort has
    "matured" past that window (day0 + window_days <= now). A user counts
    as retained if they have at least one message_sent event any time from
    day0 through day0 + window_days (cumulative, not strict-day).

    Returns (retention_pct, eligible_count, retained_count).
    retention_pct is None if no cohorts have matured into this window yet.
    """
    eligible = 0
    retained = 0

    for discord_id, day0 in cohort.items():
        window_end = day0 + timedelta(days=window_days)
        if window_end > now:
            continue  # this user's cohort hasn't reached this window yet

        eligible += 1
        user_messages = messages.get(discord_id, [])
        if any(day0 <= ts <= window_end for ts in user_messages):
            retained += 1

    pct = round((retained / eligible) * 100, 2) if eligible > 0 else None
    return pct, eligible, retained


def get_retention_metrics(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    cohort = _get_cohort_day0(db)
    messages = _get_message_timestamps(db)

    day1_pct, day1_n, day1_r = _compute_window(cohort, messages, 1, now)
    day7_pct, day7_n, day7_r = _compute_window(cohort, messages, 7, now)
    day30_pct, day30_n, day30_r = _compute_window(cohort, messages, 30, now)

    return {
        "day1_retention_pct": day1_pct,
        "day1_cohort_size": day1_n,
        "day7_retention_pct": day7_pct,
        "day7_cohort_size": day7_n,
        "day30_retention_pct": day30_pct,
        "day30_cohort_size": day30_n,
        "generated_at": now.isoformat(),
    }