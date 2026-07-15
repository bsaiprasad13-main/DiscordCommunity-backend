"""
One-off script to create the analytics_daily_snapshots table in the
live analytics DB. Run once, safe to re-run (checkfirst=True).

Does NOT touch analytics_events, analytics_users, or analytics_topics
-- only creates the new table.
"""

from analytics.database import analytics_engine
from analytics.models import AnalyticsDailySnapshot

if __name__ == "__main__":
    AnalyticsDailySnapshot.__table__.create(analytics_engine, checkfirst=True)
    print("analytics_daily_snapshots table created (or already existed).")