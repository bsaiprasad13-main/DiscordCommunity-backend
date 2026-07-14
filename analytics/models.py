import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, Index
from sqlalchemy.dialects.postgresql import UUID

from .database import AnalyticsBase as Base


class EventType(str, enum.Enum):
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    MESSAGE_SENT = "message_sent"
    REACTION_ADDED = "reaction_added"
    CAMPUSGUIDE_USED = "campusguide_used"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Client-generated UUID for idempotency. If the bot retries a POST
    # after a network failure, this lets us dedupe instead of double-counting.
    event_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)

    event_type = Column(Enum(EventType), nullable=False, index=True)
    discord_id = Column(String, nullable=False, index=True)

    # Free-form, event-specific metadata (e.g. {"channel_id": "123", "length": 42}).
    # Never put raw message content here.
    event_metadata = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_analytics_events_type_created", "event_type", "created_at"),
    )


class AnalyticsUser(Base):
    """
    Lightweight tracker for first/last activity per user, separate from
    the verification `users` table. Powers DAU/WAU/MAU and retention later
    without needing to scan the full events table each time.
    """
    __tablename__ = "analytics_users"

    discord_id = Column(String, primary_key=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    total_events = Column(Integer, nullable=False, default=0)