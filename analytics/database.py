import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

ANALYTICS_DATABASE_URL = os.environ["ANALYTICS_DATABASE_URL"]

analytics_engine = create_engine(ANALYTICS_DATABASE_URL)
AnalyticsSessionLocal = sessionmaker(bind=analytics_engine, autoflush=False, autocommit=False)

AnalyticsBase = declarative_base()


def get_analytics_db():
    db = AnalyticsSessionLocal()
    try:
        yield db
    finally:
        db.close()