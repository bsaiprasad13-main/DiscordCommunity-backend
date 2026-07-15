from analytics.database import AnalyticsSessionLocal
from analytics.metrics import get_overview_metrics

db = AnalyticsSessionLocal()
try:
    result = get_overview_metrics(db)
    print("Overview metrics:")
    for key, value in result.items():
        print(f"  {key}: {value}")
finally:
    db.close()