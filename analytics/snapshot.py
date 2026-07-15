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


def get_daily_history(db: Session) -> dict:
    """
    Returns all stored daily snapshots, oldest first. No date-range
    filtering -- all available history was requested, and there's no
    backfill so this naturally starts from whenever the job first ran.
    """
    rows = (
        db.query(AnalyticsDailySnapshot)
        .order_by(AnalyticsDailySnapshot.snapshot_date.asc())
        .all()
    )

    snapshots = [
        {
            "snapshot_date": row.snapshot_date,
            "dau": row.dau,
            "wau": row.wau,
            "mau": row.mau,
            "stickiness_pct": row.stickiness_pct,
            "day1_retention_pct": row.day1_retention_pct,
            "day7_retention_pct": row.day7_retention_pct,
            "day30_retention_pct": row.day30_retention_pct,
            "topic_counts": row.topic_counts,
        }
        for row in rows
    ]

    return {
        "snapshots": snapshots,
        "generated_at": datetime.now(timezone.utc),
    }