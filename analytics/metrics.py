from datetime import datetime, timedelta, timezone

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from .models import AnalyticsEvent, EventType


def _active_users_since(db: Session, since: datetime) -> int:
    """Count distinct discord_ids with a message_sent event since `since`."""
    return (
        db.query(func.count(distinct(AnalyticsEvent.discord_id)))
        .filter(
            AnalyticsEvent.event_type == EventType.MESSAGE_SENT,
            AnalyticsEvent.created_at >= since,
        )
        .scalar()
        or 0
    )


def _message_count_since(db: Session, since: datetime) -> int:
    """Count total message_sent events since `since` (not distinct users)."""
    return (
        db.query(func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.event_type == EventType.MESSAGE_SENT,
            AnalyticsEvent.created_at >= since,
        )
        .scalar()
        or 0
    )


def get_overview_metrics(db: Session) -> dict:
    """
    Computes DAU/WAU/MAU, stickiness, and message counts.

    All windows are rolling (last 24h / 7d / 30d from "now"), not
    calendar-aligned. Activity = message_sent only, per your earlier call.

    Queries analytics_events directly rather than the AnalyticsUser
    summary table, since AnalyticsUser isn't currently being upserted
    anywhere -- see note in chat. Safe to switch to it later once it's
    actually maintained.
    """
    now = datetime.now(timezone.utc)

    dau = _active_users_since(db, now - timedelta(days=1))
    wau = _active_users_since(db, now - timedelta(days=7))
    mau = _active_users_since(db, now - timedelta(days=30))

    stickiness = round((dau / mau) * 100, 2) if mau > 0 else 0.0

    return {
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "stickiness_pct": stickiness,
        "message_count_24h": _message_count_since(db, now - timedelta(days=1)),
        "message_count_7d": _message_count_since(db, now - timedelta(days=7)),
        "message_count_30d": _message_count_since(db, now - timedelta(days=30)),
        "generated_at": now.isoformat(),
    }