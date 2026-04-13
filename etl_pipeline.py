"""
Unified Analytics Dashboard — ETL Pipeline
===========================================
Extracts data from GA4 Data API (v1), transforms it, and loads it into PostgreSQL.

Setup:
    pip install google-analytics-data psycopg2-binary python-dotenv

Configuration:
    Create a .env file (see .env.example below) with your credentials.

Usage:
    # Pull yesterday's data (default, accounts for GA4 delay)
    python etl_pipeline.py

    # Pull a specific date
    python etl_pipeline.py --date 2026-03-15

    # Pull a date range (backfill)
    python etl_pipeline.py --start-date 2026-03-01 --end-date 2026-03-15

    # Dry run (extract only, don't load)
    python etl_pipeline.py --dry-run
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, date, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Google Analytics Data API
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric
)
from google.oauth2 import service_account

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

# GA4 Property IDs — get these from your GA4 admin panel
GA4_PROPERTIES = {
    "main_website": os.getenv("GA4_PROPERTY_ID_MAIN", "properties/XXXXXXXXX"),
    "events_platform": os.getenv("GA4_PROPERTY_ID_EVENTS", "properties/XXXXXXXXX"),
}

# Google service account credentials JSON file path
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# PostgreSQL connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "your_database"),
    "user": os.getenv("DB_USER", "your_user"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
}

# ETL settings
MAX_RETRIES = 3
RETRY_DELAY_BASE = 5  # seconds, exponential backoff
DATA_DELAY_DAYS = 2   # GA4 takes ~24-48h to process; pull from 2 days ago
BATCH_SIZE = 1000      # rows per INSERT batch

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_pipeline.log"),
    ]
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GA4 API Client
# ---------------------------------------------------------------------------
class GA4Extractor:
    """Extracts report data from the GA4 Data API."""

    # Dimensions and metrics for session-level report
    SESSION_DIMENSIONS = [
        "date", "sessionDefaultChannelGroup", "pagePath",
        "deviceCategory", "country", "city"
    ]
    SESSION_METRICS = [
        "sessions", "totalUsers", "newUsers",
        "screenPageViews", "averageSessionDuration", "bounceRate"
    ]

    # Dimensions and metrics for event-level report
    # NOTE: "customUser:user_id" requires a user-scoped custom dimension named
    # "user_id" to be registered in GA4 Admin → Custom Definitions → Custom Dimensions.
    # If this hasn't been set up yet, set ENABLE_CUSTOM_USER_ID=false in .env
    # and the pipeline will skip it (custom_user_id will be NULL in the DB).
    EVENT_DIMENSIONS_BASE = [
        "date", "eventName", "pagePath", "deviceCategory"
    ]
    CUSTOM_USER_DIMENSION = "customUser:user_id"
    EVENT_METRICS = [
        "eventCount", "totalUsers"
    ]

    def __init__(self):
        """Initialize the GA4 client with service account credentials."""
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        self.client = BetaAnalyticsDataClient(credentials=credentials)
        logger.info("GA4 API client initialized")

    def _run_report_with_retry(self, request: RunReportRequest) -> list[dict]:
        """Execute a GA4 report request with retry logic."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.run_report(request)
                rows = self._parse_response(response)
                logger.info(f"  Got {len(rows)} rows (attempt {attempt})")
                return rows
            except Exception as e:
                if attempt == MAX_RETRIES:
                    logger.error(f"  Failed after {MAX_RETRIES} attempts: {e}")
                    raise
                wait = RETRY_DELAY_BASE * (2 ** (attempt - 1))
                logger.warning(f"  Attempt {attempt} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        return []

    def _parse_response(self, response) -> list[dict]:
        """Convert GA4 API response into a list of dicts."""
        dim_headers = [h.name for h in response.dimension_headers]
        met_headers = [h.name for h in response.metric_headers]
        rows = []
        for row in response.rows:
            record = {}
            for i, dim in enumerate(row.dimension_values):
                record[dim_headers[i]] = dim.value
            for i, met in enumerate(row.metric_values):
                record[met_headers[i]] = met.value
            rows.append(record)
        return rows

    def extract_sessions(self, property_id: str, target_date: date) -> list[dict]:
        """Extract session-level data for a single date and property."""
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info(f"Extracting sessions: {property_id} for {date_str}")

        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
            dimensions=[Dimension(name=d) for d in self.SESSION_DIMENSIONS],
            metrics=[Metric(name=m) for m in self.SESSION_METRICS],
            limit=100000,
        )
        return self._run_report_with_retry(request)

    def extract_events(self, property_id: str, target_date: date) -> list[dict]:
        """Extract event-level data for a single date and property."""
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info(f"Extracting events: {property_id} for {date_str}")

        # Build dimensions list, optionally including custom user ID
        dimensions = [Dimension(name=d) for d in self.EVENT_DIMENSIONS_BASE]
        enable_custom_uid = os.getenv("ENABLE_CUSTOM_USER_ID", "true").lower() == "true"
        if enable_custom_uid:
            dimensions.append(Dimension(name=self.CUSTOM_USER_DIMENSION))

        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
            dimensions=dimensions,
            metrics=[Metric(name=m) for m in self.EVENT_METRICS],
            limit=100000,
        )
        try:
            return self._run_report_with_retry(request)
        except Exception as e:
            # If the custom dimension doesn't exist yet, retry without it
            if enable_custom_uid and "customUser:user_id" in str(e):
                logger.warning(f"  Custom dimension 'user_id' not found in GA4. "
                               f"Retrying without it. Set ENABLE_CUSTOM_USER_ID=false to skip.")
                dimensions = [Dimension(name=d) for d in self.EVENT_DIMENSIONS_BASE]
                request = RunReportRequest(
                    property=property_id,
                    date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
                    dimensions=dimensions,
                    metrics=[Metric(name=m) for m in self.EVENT_METRICS],
                    limit=100000,
                )
                return self._run_report_with_retry(request)
            raise


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------
class Transformer:
    """Cleans and maps raw GA4 data to our database schema."""

    @staticmethod
    def transform_sessions(raw_rows: list[dict], source_label: str, target_date: date) -> list[tuple]:
        """Transform raw session data into tuples for PostgreSQL INSERT."""
        result = []
        for row in raw_rows:
            result.append((
                target_date,
                source_label,
                row.get("sessionDefaultChannelGroup", "Unknown"),
                row.get("pagePath", "/"),
                row.get("deviceCategory", "unknown"),
                row.get("country", "Unknown"),
                row.get("city", "Unknown"),
                int(row.get("sessions", 0)),
                int(row.get("totalUsers", 0)),
                int(row.get("newUsers", 0)),
                int(row.get("screenPageViews", 0)),
                float(row.get("averageSessionDuration", 0)),
                float(row.get("bounceRate", 0)),
                datetime.utcnow(),
            ))
        return result

    @staticmethod
    def transform_events(raw_rows: list[dict], source_label: str, target_date: date) -> list[tuple]:
        """Transform raw event data into tuples for PostgreSQL INSERT."""
        result = []
        for row in raw_rows:
            custom_uid = row.get("customUser:user_id")
            if custom_uid in ("(not set)", "", None):
                custom_uid = None

            result.append((
                target_date,
                source_label,
                row.get("eventName", "unknown"),
                row.get("pagePath", "/"),
                row.get("deviceCategory", "unknown"),
                int(row.get("eventCount", 0)),
                int(row.get("totalUsers", 0)),
                custom_uid,
                datetime.utcnow(),
            ))
        return result


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
class Loader:
    """Loads transformed data into PostgreSQL with upsert logic."""

    UPSERT_SESSIONS = """
        INSERT INTO analytics.ga4_sessions
            (report_date, property_source, channel_group, page_path,
             device_category, country, city, sessions, total_users,
             new_users, pageviews, avg_session_duration, bounce_rate, fetched_at)
        VALUES %s
        ON CONFLICT (report_date, property_source, channel_group, page_path, device_category, country, city)
        DO UPDATE SET
            sessions = EXCLUDED.sessions,
            total_users = EXCLUDED.total_users,
            new_users = EXCLUDED.new_users,
            pageviews = EXCLUDED.pageviews,
            avg_session_duration = EXCLUDED.avg_session_duration,
            bounce_rate = EXCLUDED.bounce_rate,
            fetched_at = EXCLUDED.fetched_at
    """

    UPSERT_EVENTS = """
        INSERT INTO analytics.ga4_events
            (report_date, property_source, event_name, page_path,
             device_category, event_count, unique_users, custom_user_id, fetched_at)
        VALUES %s
        ON CONFLICT (report_date, property_source, event_name, page_path, device_category, custom_user_id)
        DO UPDATE SET
            event_count = EXCLUDED.event_count,
            unique_users = EXCLUDED.unique_users,
            fetched_at = EXCLUDED.fetched_at
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        logger.info("PostgreSQL connection established")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("PostgreSQL connection closed")

    def load_sessions(self, rows: list[tuple]) -> int:
        """Upsert session rows into PostgreSQL. Returns number of rows affected."""
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                execute_values(cur, self.UPSERT_SESSIONS, batch)
            self.conn.commit()
        logger.info(f"  Loaded {len(rows)} session rows")
        return len(rows)

    def load_events(self, rows: list[tuple]) -> int:
        """Upsert event rows into PostgreSQL. Returns number of rows affected."""
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                execute_values(cur, self.UPSERT_EVENTS, batch)
            self.conn.commit()
        logger.info(f"  Loaded {len(rows)} event rows")
        return len(rows)

    def log_run(self, target_date: date, property_source: str,
                rows_extracted: int, rows_loaded: int,
                status: str, error_message: Optional[str] = None,
                started_at: Optional[datetime] = None):
        """Write an entry to the ETL run log."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analytics.etl_run_log
                    (run_started_at, run_ended_at, target_date, property_source,
                     rows_extracted, rows_loaded, status, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                started_at or datetime.utcnow(),
                datetime.utcnow(),
                target_date,
                property_source,
                rows_extracted,
                rows_loaded,
                status,
                error_message,
            ))
            self.conn.commit()

    def refresh_views(self):
        """Refresh materialized views after loading new data."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT analytics.refresh_all_views();")
            self.conn.commit()
        logger.info("Materialized views refreshed")


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------
class ETLPipeline:
    """Orchestrates the full Extract → Transform → Load flow."""

    def __init__(self, dry_run: bool = False):
        self.extractor = GA4Extractor()
        self.transformer = Transformer()
        self.loader = None if dry_run else Loader()
        self.dry_run = dry_run

    def run_for_date(self, target_date: date):
        """Run the full ETL pipeline for a single date, both properties."""
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Starting ETL for {target_date}")

        for source_label, property_id in GA4_PROPERTIES.items():
            started_at = datetime.utcnow()
            total_extracted = 0
            total_loaded = 0

            try:
                # --- EXTRACT ---
                raw_sessions = self.extractor.extract_sessions(property_id, target_date)
                raw_events = self.extractor.extract_events(property_id, target_date)
                total_extracted = len(raw_sessions) + len(raw_events)

                # --- TRANSFORM ---
                session_rows = self.transformer.transform_sessions(raw_sessions, source_label, target_date)
                event_rows = self.transformer.transform_events(raw_events, source_label, target_date)

                if self.dry_run:
                    logger.info(f"  [DRY RUN] Would load {len(session_rows)} sessions, {len(event_rows)} events")
                    # Print sample data
                    if session_rows:
                        logger.info(f"  Sample session row: {session_rows[0][:6]}...")
                    if event_rows:
                        logger.info(f"  Sample event row: {event_rows[0][:5]}...")
                    continue

                # --- LOAD ---
                loaded_sessions = self.loader.load_sessions(session_rows)
                loaded_events = self.loader.load_events(event_rows)
                total_loaded = loaded_sessions + loaded_events

                # Log success
                self.loader.log_run(
                    target_date=target_date,
                    property_source=source_label,
                    rows_extracted=total_extracted,
                    rows_loaded=total_loaded,
                    status="success",
                    started_at=started_at,
                )
                logger.info(f"  {source_label}: extracted={total_extracted}, loaded={total_loaded}")

            except Exception as e:
                logger.error(f"  FAILED for {source_label}: {e}")
                if self.loader:
                    self.loader.log_run(
                        target_date=target_date,
                        property_source=source_label,
                        rows_extracted=total_extracted,
                        rows_loaded=total_loaded,
                        status="failed",
                        error_message=str(e),
                        started_at=started_at,
                    )

        # Refresh materialized views after all properties are loaded
        if not self.dry_run and self.loader:
            try:
                self.loader.refresh_views()
            except Exception as e:
                logger.warning(f"View refresh failed (non-fatal): {e}")

    def run_for_range(self, start_date: date, end_date: date):
        """Run the pipeline for each date in a range (inclusive)."""
        current = start_date
        while current <= end_date:
            self.run_for_date(current)
            current += timedelta(days=1)

    def close(self):
        if self.loader:
            self.loader.close()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="GA4 → PostgreSQL ETL Pipeline")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Target date (YYYY-MM-DD). Default: 2 days ago."
    )
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="Start date for backfill range (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="End date for backfill range (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract and transform only, don't load into database."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pipeline = ETLPipeline(dry_run=args.dry_run)

    try:
        if args.start_date and args.end_date:
            start = date.fromisoformat(args.start_date)
            end = date.fromisoformat(args.end_date)
            logger.info(f"Backfill mode: {start} to {end}")
            pipeline.run_for_range(start, end)
        elif args.date:
            target = date.fromisoformat(args.date)
            pipeline.run_for_date(target)
        else:
            # Default: pull data from 2 days ago
            target = date.today() - timedelta(days=DATA_DELAY_DAYS)
            pipeline.run_for_date(target)
    finally:
        pipeline.close()

    logger.info("ETL pipeline complete.")


if __name__ == "__main__":
    main()
