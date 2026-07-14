from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .database import get_analytics_db
from .models import AnalyticsEvent, AnalyticsUser
from .schemas import EventIn, EventAck

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/events", response_model=EventAck)
def ingest_event(payload: EventIn, db: Session = Depends(get_analytics_db)):
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)

    # Idempotent insert: ON CONFLICT (event_id) DO NOTHING
    stmt = pg_insert(AnalyticsEvent).values(
        event_id=payload.event_id,
        event_type=payload.event_type,
        discord_id=payload.discord_id,
        event_metadata=payload.metadata,
        created_at=occurred_at,
    ).on_conflict_do_nothing(index_elements=["event_id"])

    result = db.execute(stmt)
    db.commit()

    is_new = result.rowcount == 1

    if is_new:
        user_stmt = pg_insert(AnalyticsUser).values(
            discord_id=payload.discord_id,
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

    return EventAck(
        event_id=payload.event_id,
        status="recorded" if is_new else "duplicate",
    )