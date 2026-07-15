"""
Manual one-off script to run the daily snapshot job immediately,
without waiting for the scheduled 12:05 AM run. Useful for testing.

Run with: python run_snapshot_now.py
"""

from analytics.database import AnalyticsSessionLocal
from analytics.snapshot import compute_daily_snapshot

if __name__ == "__main__":
    db = AnalyticsSessionLocal()
    try:
        snapshot = compute_daily_snapshot(db)
        print(f"Snapshot computed for {snapshot.snapshot_date}:")
        print(f"  DAU={snapshot.dau}  WAU={snapshot.wau}  MAU={snapshot.mau}  Stickiness={snapshot.stickiness_pct}%")
        print(f"  Retention: day1={snapshot.day1_retention_pct}  day7={snapshot.day7_retention_pct}  day30={snapshot.day30_retention_pct}")
        print(f"  Topics: {snapshot.topic_counts}")
    finally:
        db.close()