-- ============================================================================
-- Unified Analytics Dashboard — Database Schema
-- Digital Ecosystem & Traffic Unit
-- Team: Marco, Vivan, Sofia
-- 
-- Run this script against your local PostgreSQL instance to create
-- all analytics tables. This does NOT touch the existing public schema
-- (events, registrations, users) — everything lives in a separate
-- "analytics" schema.
--
-- Usage:  psql -U your_user -d your_db -f schema.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Create the analytics schema (keeps our tables isolated)
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS analytics;

-- ----------------------------------------------------------------------------
-- 2. GA4 Session-Level Data
--    Stores daily aggregated session metrics per property/channel/page/device.
--    The ETL pipeline upserts into this table daily.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.ga4_sessions (
    id                    SERIAL PRIMARY KEY,
    report_date           DATE NOT NULL,
    property_source       VARCHAR(50) NOT NULL,       -- 'main_website' or 'events_platform'
    channel_group         VARCHAR(100),                -- Organic Search, Direct, Referral, etc.
    page_path             VARCHAR(500),                -- e.g. /events/123, /about
    device_category       VARCHAR(20),                 -- desktop, mobile, tablet
    country               VARCHAR(100),
    city                  VARCHAR(100),
    sessions              INTEGER DEFAULT 0,
    total_users           INTEGER DEFAULT 0,
    new_users             INTEGER DEFAULT 0,
    pageviews             INTEGER DEFAULT 0,
    avg_session_duration  NUMERIC(10, 2) DEFAULT 0,   -- seconds
    bounce_rate           NUMERIC(5, 4) DEFAULT 0,    -- 0.0000 to 1.0000
    fetched_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint for upsert (prevents duplicates on re-runs)
ALTER TABLE analytics.ga4_sessions
    DROP CONSTRAINT IF EXISTS uq_ga4_sessions_natural_key;
ALTER TABLE analytics.ga4_sessions
    ADD CONSTRAINT uq_ga4_sessions_natural_key
    UNIQUE (report_date, property_source, channel_group, page_path, device_category, country, city);

-- Indexes for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_ga4_sessions_date
    ON analytics.ga4_sessions (report_date);
CREATE INDEX IF NOT EXISTS idx_ga4_sessions_source
    ON analytics.ga4_sessions (property_source);
CREATE INDEX IF NOT EXISTS idx_ga4_sessions_date_source
    ON analytics.ga4_sessions (report_date, property_source);
CREATE INDEX IF NOT EXISTS idx_ga4_sessions_channel
    ON analytics.ga4_sessions (channel_group);


-- ----------------------------------------------------------------------------
-- 3. GA4 Event-Level Data
--    Stores event counts from GA4 — this is what powers the funnel analysis.
--    custom_user_id links GA4 events to internal users (when logged in).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.ga4_events (
    id                SERIAL PRIMARY KEY,
    report_date       DATE NOT NULL,
    property_source   VARCHAR(50) NOT NULL,
    event_name        VARCHAR(100) NOT NULL,          -- page_view, session_start, begin_registration, etc.
    page_path         VARCHAR(500),
    device_category   VARCHAR(20),
    event_count       INTEGER DEFAULT 0,
    unique_users      INTEGER DEFAULT 0,
    custom_user_id    VARCHAR(100),                    -- internal user ID passed via GA4 custom dimension (nullable)
    fetched_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint for upsert
ALTER TABLE analytics.ga4_events
    DROP CONSTRAINT IF EXISTS uq_ga4_events_natural_key;
ALTER TABLE analytics.ga4_events
    ADD CONSTRAINT uq_ga4_events_natural_key
    UNIQUE (report_date, property_source, event_name, page_path, device_category, custom_user_id);

-- Indexes for funnel queries
CREATE INDEX IF NOT EXISTS idx_ga4_events_date
    ON analytics.ga4_events (report_date);
CREATE INDEX IF NOT EXISTS idx_ga4_events_name
    ON analytics.ga4_events (event_name);
CREATE INDEX IF NOT EXISTS idx_ga4_events_date_name
    ON analytics.ga4_events (report_date, event_name);
CREATE INDEX IF NOT EXISTS idx_ga4_events_user_id
    ON analytics.ga4_events (custom_user_id)
    WHERE custom_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ga4_events_source
    ON analytics.ga4_events (property_source);


-- ----------------------------------------------------------------------------
-- 4. ETL Run Log
--    Every pipeline execution is logged here for monitoring and debugging.
--    If a run fails, the error_message column tells you why.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.etl_run_log (
    id               SERIAL PRIMARY KEY,
    run_started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_ended_at     TIMESTAMPTZ,
    target_date      DATE NOT NULL,                   -- which date's data was fetched
    property_source  VARCHAR(50) NOT NULL,
    rows_extracted   INTEGER DEFAULT 0,
    rows_loaded      INTEGER DEFAULT 0,
    status           VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, success, failed, partial
    error_message    TEXT,
    pipeline_version VARCHAR(20) DEFAULT '1.0'
);

CREATE INDEX IF NOT EXISTS idx_etl_run_log_date
    ON analytics.etl_run_log (target_date);
CREATE INDEX IF NOT EXISTS idx_etl_run_log_status
    ON analytics.etl_run_log (status);


-- ----------------------------------------------------------------------------
-- 5. Funnel Stage Definitions (reference table)
--    Stores the named funnel stages so queries and the dashboard can reference
--    them by stage_order rather than hardcoding event names everywhere.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.funnel_stages (
    id              SERIAL PRIMARY KEY,
    stage_order     INTEGER NOT NULL UNIQUE,           -- 1, 2, 3, 4, 5
    stage_name      VARCHAR(100) NOT NULL,
    ga4_event_name  VARCHAR(100),                      -- the GA4 event that maps to this stage
    ga4_page_pattern VARCHAR(200),                     -- regex or LIKE pattern for page paths
    property_source VARCHAR(50),                       -- which property this stage applies to
    description     TEXT
);

-- Pre-populate the five funnel stages defined in the architecture document
INSERT INTO analytics.funnel_stages (stage_order, stage_name, ga4_event_name, ga4_page_pattern, property_source, description)
VALUES
    (1, 'Landing',               'session_start',          '%',              'main_website',     'First visit to any page on the main website'),
    (2, 'Event Discovery',       'page_view',              '/events%',       'any',              'User views events listing pages (/events, /events/, /events?page=N). Note: overlap with stage 3 is handled by query ordering — a user who reaches stage 3 is counted there, not here.'),
    (3, 'Event Detail View',     'page_view',              '/events/_%',     'events_platform',  'User views a specific event detail page (e.g. /events/123)'),
    (4, 'Registration Start',    'begin_registration',     NULL,             'events_platform',  'User clicks the Register button on an event'),
    (5, 'Registration Complete', 'complete_registration',  NULL,             'events_platform',  'User completes the registration form')
ON CONFLICT DO NOTHING;


-- ----------------------------------------------------------------------------
-- 6. Materialized View: Daily Funnel Summary
--    Pre-calculates funnel metrics per day so the dashboard queries are fast.
--    Refresh this after each ETL run: REFRESH MATERIALIZED VIEW CONCURRENTLY ...
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_daily_funnel AS
WITH event_stage_matches AS (
    -- Match each event row to ALL possible funnel stages
    SELECT
        e.report_date,
        e.id AS event_id,
        e.unique_users,
        fs.stage_order,
        fs.stage_name
    FROM analytics.ga4_events e
    JOIN analytics.funnel_stages fs
        ON e.event_name = fs.ga4_event_name
        AND (fs.ga4_page_pattern IS NULL OR e.page_path LIKE fs.ga4_page_pattern)
        AND (fs.property_source = 'any' OR e.property_source = fs.property_source)
),
best_match AS (
    -- For each event row, keep only the HIGHEST (most specific) stage it matches.
    -- This prevents /events/123 from counting in both stage 2 and stage 3.
    SELECT DISTINCT ON (report_date, event_id)
        report_date,
        event_id,
        unique_users,
        stage_order,
        stage_name
    FROM event_stage_matches
    ORDER BY report_date, event_id, stage_order DESC
),
stage_counts AS (
    SELECT
        report_date,
        stage_order,
        stage_name,
        SUM(unique_users) AS users_at_stage
    FROM best_match
    GROUP BY report_date, stage_order, stage_name
)
SELECT
    sc.report_date,
    sc.stage_order,
    sc.stage_name,
    sc.users_at_stage,
    -- Conversion rate: users at this stage / users at previous stage
    CASE
        WHEN LAG(sc.users_at_stage) OVER (PARTITION BY sc.report_date ORDER BY sc.stage_order) > 0
        THEN ROUND(
            sc.users_at_stage::NUMERIC /
            LAG(sc.users_at_stage) OVER (PARTITION BY sc.report_date ORDER BY sc.stage_order),
            4
        )
        ELSE NULL
    END AS conversion_rate,
    -- Drop-off rate: 1 - conversion_rate
    CASE
        WHEN LAG(sc.users_at_stage) OVER (PARTITION BY sc.report_date ORDER BY sc.stage_order) > 0
        THEN ROUND(
            1 - (sc.users_at_stage::NUMERIC /
            LAG(sc.users_at_stage) OVER (PARTITION BY sc.report_date ORDER BY sc.stage_order)),
            4
        )
        ELSE NULL
    END AS dropoff_rate
FROM stage_counts sc
ORDER BY sc.report_date, sc.stage_order;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_funnel_pk
    ON analytics.mv_daily_funnel (report_date, stage_order);


-- ----------------------------------------------------------------------------
-- 7. Materialized View: Monthly Traffic Summary
--    Aggregates traffic by month and property for the seasonal trends dashboard.
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_monthly_traffic AS
SELECT
    DATE_TRUNC('month', report_date)::DATE  AS month,
    property_source,
    SUM(sessions)                           AS total_sessions,
    SUM(total_users)                        AS total_users,
    SUM(new_users)                          AS total_new_users,
    SUM(pageviews)                          AS total_pageviews,
    ROUND(AVG(avg_session_duration), 2)     AS avg_session_duration,
    ROUND(AVG(bounce_rate), 4)              AS avg_bounce_rate
FROM analytics.ga4_sessions
GROUP BY DATE_TRUNC('month', report_date), property_source
ORDER BY month, property_source;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_monthly_traffic_pk
    ON analytics.mv_monthly_traffic (month, property_source);


-- ----------------------------------------------------------------------------
-- 8. Helper function: Refresh all materialized views
--    Call this after each ETL run: SELECT analytics.refresh_all_views();
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION analytics.refresh_all_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_daily_funnel;
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_monthly_traffic;
END;
$$ LANGUAGE plpgsql;


-- ----------------------------------------------------------------------------
-- 9. Grants (adjust role names to match your setup)
--    Uncomment and modify these lines when deploying.
-- ----------------------------------------------------------------------------
-- GRANT USAGE ON SCHEMA analytics TO your_app_role;
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO your_app_role;
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO readonly_dashboard_role;
-- GRANT INSERT, UPDATE ON analytics.ga4_sessions, analytics.ga4_events, analytics.etl_run_log TO etl_role;


-- ============================================================================
-- DONE. Run this file with:
--   psql -U your_user -d your_db -f schema.sql
--
-- After each ETL run, refresh the views:
--   SELECT analytics.refresh_all_views();
-- ============================================================================
