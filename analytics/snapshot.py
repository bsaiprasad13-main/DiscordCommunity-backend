from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from .metrics import get_overview_metrics, get_topic_metrics
from .retention import get_retention_metrics
from .models import AnalyticsDailySnapshot


def compute_daily_snapshot(db: Session, for_date: date = None) -> AnalyticsDailySnapshot:
    """
    Computes today's (or a given date's) Overview + Retention + Topics
    metrics and upserts a row in analytics_daily_snapshots.

    Upserts by snapshot_date -- safe to call more than once on the same
    day (e.g. manual test run + scheduled run), won't create duplicates.

    Note: this reuses the existing metrics functions as-is. Those
    functions compute rolling/all-time metrics as of "now", not
    specifically "as of end of for_date" -- so running this for a
    past date would just recompute current numbers, not reconstruct
    history. Fine given we're not backfilling.
    """
    if for_date is None:
        for_date = datetime.now(timezone.utc).date()

    overview = get_overview_metrics(db)
    retention = get_retention_metrics(db)
    topics = get_topic_metrics(db)

    snapshot = (
        db.query(AnalyticsDailySnapshot)
        .filter(AnalyticsDailySnapshot.snapshot_date == for_date)
        .first()
    )
    if snapshot is None:
        snapshot = AnalyticsDailySnapshot(snapshot_date=for_date)
        db.add(snapshot)

    snapshot.dau = overview["dau"]
    snapshot.wau = overview["wau"]
    snapshot.mau = overview["mau"]
    snapshot.stickiness_pct = overview["stickiness_pct"]

    snapshot.day1_retention_pct = retention["day1_retention_pct"]
    snapshot.day7_retention_pct = retention["day7_retention_pct"]
    snapshot.day30_retention_pct = retention["day30_retention_pct"]
    snapshot.day1_cohort_size = retention["day1_cohort_size"]
    snapshot.day7_cohort_size = retention["day7_cohort_size"]
    snapshot.day30_cohort_size = retention["day30_cohort_size"]

    snapshot.topic_counts = topics["topic_counts"]
    snapshot.created_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(snapshot)
    return snapshot