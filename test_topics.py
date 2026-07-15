import uuid

from analytics.database import AnalyticsSessionLocal
from analytics.ingest import record_event
from analytics.models import EventType, AnalyticsTopic

db = AnalyticsSessionLocal()
try:
    # Use a fixed event_id so we can query for it and also test the
    # duplicate-retry path deliberately (unlike test_ingest.py, which
    # uses a fresh event_id each call to simulate separate events).
    test_event_id = uuid.uuid4()

    is_new = record_event(
        db,
        event_type=EventType.MESSAGE_SENT,
        discord_id="test_user_phase4",
        metadata={
            "channel_id": "123",
            "length": 42,
            "topics": ["placements", "internships"],
        },
        event_id=test_event_id,
    )
    print(f"First call - is_new: {is_new}")  # expect True

    rows = db.query(AnalyticsTopic).filter(AnalyticsTopic.event_id == test_event_id).all()
    print(f"Topic rows after first call: {[r.topic for r in rows]}")  # expect ['placements', 'internships']

    # Retry with the SAME event_id (simulates the bot retrying a POST
    # after a network blip). Must be treated as a duplicate, and must
    # NOT double-write topic rows.
    is_new_retry = record_event(
        db,
        event_type=EventType.MESSAGE_SENT,
        discord_id="test_user_phase4",
        metadata={
            "channel_id": "123",
            "length": 42,
            "topics": ["placements", "internships"],
        },
        event_id=test_event_id,
    )
    print(f"Retry call - is_new: {is_new_retry}")  # expect False

    rows_after_retry = db.query(AnalyticsTopic).filter(AnalyticsTopic.event_id == test_event_id).all()
    print(f"Topic rows after retry: {[r.topic for r in rows_after_retry]}")  # expect still just 2 rows, unchanged
finally:
    db.close()