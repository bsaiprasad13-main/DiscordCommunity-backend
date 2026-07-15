from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .database import get_analytics_db
from .ingest import record_event
from .metrics import get_overview_metrics, get_topic_metrics
from .retention import get_retention_metrics
from .snapshot import get_daily_history
from .schemas import EventIn, EventAck, OverviewOut, RetentionOut, TopicsOut, DailyHistoryOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/events", response_model=EventAck)
def ingest_event(payload: EventIn, db: Session = Depends(get_analytics_db)):
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)

    is_new = record_event(
        db,
        event_type=payload.event_type,
        discord_id=payload.discord_id,
        metadata=payload.metadata,
        occurred_at=occurred_at,
        event_id=payload.event_id,
    )

    return EventAck(
        event_id=payload.event_id,
        status="recorded" if is_new else "duplicate",
    )


@router.get("/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_analytics_db)):
    return get_overview_metrics(db)


@router.get("/retention", response_model=RetentionOut)
def retention(db: Session = Depends(get_analytics_db)):
    return get_retention_metrics(db)


@router.get("/topics", response_model=TopicsOut)
def topics(db: Session = Depends(get_analytics_db)):
    return get_topic_metrics(db)


@router.get("/history", response_model=DailyHistoryOut)
def history(db: Session = Depends(get_analytics_db)):
    return get_daily_history(db)