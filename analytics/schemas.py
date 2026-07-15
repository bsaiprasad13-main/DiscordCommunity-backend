import uuid
from datetime import datetime, date
from typing import Optional, Dict, List
from pydantic import BaseModel, Field

from .models import EventType


class EventIn(BaseModel):
    event_id: uuid.UUID = Field(..., description="Client-generated UUID, used for idempotency")
    event_type: EventType
    discord_id: str
    metadata: dict = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None  # bot's local timestamp; falls back to server time


class EventAck(BaseModel):
    event_id: uuid.UUID
    status: str  # "recorded" | "duplicate"


class OverviewOut(BaseModel):
    dau: int
    wau: int
    mau: int
    stickiness_pct: float
    message_count_24h: int
    message_count_7d: int
    message_count_30d: int
    generated_at: datetime

class RetentionOut(BaseModel):
    day1_retention_pct: Optional[float]
    day1_cohort_size: int
    day7_retention_pct: Optional[float]
    day7_cohort_size: int
    day30_retention_pct: Optional[float]
    day30_cohort_size: int
    generated_at: datetime

class TopicsOut(BaseModel):
    topic_counts: Dict[str, int]
    generated_at: datetime


class DailySnapshotOut(BaseModel):
    snapshot_date: date
    dau: int
    wau: int
    mau: int
    stickiness_pct: float
    day1_retention_pct: Optional[float]
    day7_retention_pct: Optional[float]
    day30_retention_pct: Optional[float]
    topic_counts: Dict[str, int]


class DailyHistoryOut(BaseModel):
    snapshots: List[DailySnapshotOut]
    generated_at: datetime