import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import AnalyticsEvent, AnalyticsUser, AnalyticsTopic, EventType


def record_event(
    db: Session,
    event_type: EventType,
    discord_id: str,
    metadata: Optional[dict] = None,
    occurred_at: Optional[datetime] = None,
    event_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Shared idempotent-insert logic, used by both the HTTP /analytics/events
    route (router.py) and direct in-process calls (e.g. from main.py's
    verify-otp flow). Returns True if a new event was recorded, False if
    it was a duplicate.

    Does NOT swallow exceptions itself -- callers making in-process calls
    from critical paths (like verification) are responsible for wrapping
    this in their own try/except so a DB hiccup here can never break the
    calling flow. The HTTP route doesn't need that wrapper since FastAPI's
    own error handling covers it.
    """
    event_id = event_id or uuid.uuid4()
    occurred_at = occurred_at or datetime.now(timezone.utc)
    metadata = metadata or {}

    stmt = pg_insert(AnalyticsEvent).values(
        event_id=event_id,
        event_type=event_type,
        discord_id=discord_id,
        event_metadata=metadata,
        created_at=occurred_at,
    ).on_conflict_do_nothing(index_elements=["event_id"])

    result = db.execute(stmt)
    db.commit()

    is_new = result.rowcount == 1

    if is_new:
        user_stmt = pg_insert(AnalyticsUser).values(
            discord_id=discord_id,
            first_seen_at=occurred_at,
            last_seen_at=occurred_at,
            total_events=1,
        ).on_conflict_do_update(
            index_elements=["discord_id"],
            set_={
                "last_seen_at": occurred_at,
                "total_events": AnalyticsUser.total_events + 1,
            },
        )
        db.execute(user_stmt)
        db.commit()

        # Write one row per topic tag, if this event carried any.
        # Only runs for genuinely new events -- a retried/duplicate POST
        # (is_new == False) must never double-write topic rows.
        topics = metadata.get("topics")
        if topics:
            db.execute(
                AnalyticsTopic.__table__.insert(),
                [{"event_id": event_id, "topic": topic} for topic in topics],
            )
            db.commit()

    return is_new