"""
One-off script to create the analytics_topics table in the live
analytics DB. Run once, then this file can be left in the repo for
reference (same pattern as add_enum_value.py) — running it again is
safe, since checkfirst=True means it does nothing if the table
already exists.

Does NOT touch analytics_events or analytics_users — only creates
the new table.
"""

from analytics.database import analytics_engine
from analytics.models import AnalyticsTopic

if __name__ == "__main__":
    AnalyticsTopic.__table__.create(analytics_engine, checkfirst=True)
    print("analytics_topics table created (or already existed).")