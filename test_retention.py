from analytics.database import AnalyticsSessionLocal
from analytics.retention import get_retention_metrics

db = AnalyticsSessionLocal()
try:
    result = get_retention_metrics(db)
    print("Retention metrics:")
    for key, value in result.items():
        print(f"  {key}: {value}")
finally:
    db.close()