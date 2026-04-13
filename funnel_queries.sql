-- ============================================================================
-- Funnel Analysis Queries
-- Unified Analytics Dashboard — Digital Ecosystem & Traffic Unit
--
-- These queries power the dashboard. They calculate:
--   1. Funnel conversion rates and drop-off per stage
--   2. Daily/weekly/monthly funnel trends
--   3. Traffic overview across both properties
--   4. Seasonal patterns
--   5. Cross-property user flow
--   6. Funnel validated against internal registration data
-- ============================================================================


-- ============================================================================
-- QUERY 1: Overall Funnel Summary (last 30 days)
-- Shows users at each stage, conversion rate, and drop-off
-- ============================================================================
WITH event_stage_matches AS (
    SELECT
        e.id AS event_id,
        e.unique_users,
        fs.stage_order,
        fs.stage_name
    FROM analytics.ga4_events e
    JOIN analytics.funnel_stages fs
        ON e.event_name = fs.ga4_event_name
        AND (fs.ga4_page_pattern IS NULL OR e.page_path LIKE fs.ga4_page_pattern)
        AND (fs.property_source = 'any' OR e.property_source = fs.property_source)
    WHERE e.report_date >= CURRENT_DATE - INTERVAL '30 days'
),
best_match AS (
    -- Keep only the most specific (highest stage_order) match per event row
    SELECT DISTINCT ON (event_id)
        event_id, unique_users, stage_order, stage_name
    FROM event_stage_matches
    ORDER BY event_id, stage_order DESC
),
funnel AS (
    SELECT
        stage_order,
        stage_name,
        SUM(unique_users) AS users_at_stage
    FROM best_match
    GROUP BY stage_order, stage_name
)
SELECT
    stage_order,
    stage_name,
    users_at_stage,
    -- Conversion from previous stage
    ROUND(
        users_at_stage::NUMERIC /
        NULLIF(LAG(users_at_stage) OVER (ORDER BY stage_order), 0) * 100,
        1
    ) AS conversion_pct,
    -- Drop-off from previous stage
    ROUND(
        (1 - users_at_stage::NUMERIC /
        NULLIF(LAG(users_at_stage) OVER (ORDER BY stage_order), 0)) * 100,
        1
    ) AS dropoff_pct,
    -- Overall conversion (from stage 1)
    ROUND(
        users_at_stage::NUMERIC /
        NULLIF(FIRST_VALUE(users_at_stage) OVER (ORDER BY stage_order), 0) * 100,
        1
    ) AS overall_conversion_pct
FROM funnel
ORDER BY stage_order;


-- ============================================================================
-- QUERY 2: Daily Funnel Trend (from materialized view)
-- Use this for the funnel-over-time line chart
-- ============================================================================
SELECT
    report_date,
    stage_order,
    stage_name,
    users_at_stage,
    ROUND(conversion_rate * 100, 1) AS conversion_pct,
    ROUND(dropoff_rate * 100, 1)    AS dropoff_pct
FROM analytics.mv_daily_funnel
WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY report_date, stage_order;


-- ============================================================================
-- QUERY 3: Biggest Drop-Off Point (last 30 days)
-- Identifies which funnel stage loses the most users
-- ============================================================================
WITH event_stage_matches AS (
    SELECT
        e.id AS event_id,
        e.unique_users,
        fs.stage_order,
        fs.stage_name
    FROM analytics.ga4_events e
    JOIN analytics.funnel_stages fs
        ON e.event_name = fs.ga4_event_name
        AND (fs.ga4_page_pattern IS NULL OR e.page_path LIKE fs.ga4_page_pattern)
        AND (fs.property_source = 'any' OR e.property_source = fs.property_source)
    WHERE e.report_date >= CURRENT_DATE - INTERVAL '30 days'
),
best_match AS (
    SELECT DISTINCT ON (event_id)
        event_id, unique_users, stage_order, stage_name
    FROM event_stage_matches
    ORDER BY event_id, stage_order DESC
),
funnel AS (
    SELECT
        stage_order,
        stage_name,
        SUM(unique_users) AS users_at_stage
    FROM best_match
    GROUP BY stage_order, stage_name
)
SELECT
    stage_name AS biggest_dropoff_stage,
    users_at_stage AS users_remaining,
    LAG(users_at_stage) OVER (ORDER BY stage_order) - users_at_stage AS users_lost,
    ROUND(
        (LAG(users_at_stage) OVER (ORDER BY stage_order) - users_at_stage)::NUMERIC /
        NULLIF(LAG(users_at_stage) OVER (ORDER BY stage_order), 0) * 100,
        1
    ) AS dropoff_pct
FROM funnel
ORDER BY users_lost DESC NULLS LAST
LIMIT 1;


-- ============================================================================
-- QUERY 4: Traffic Overview — Daily Sessions by Property
-- Powers the main traffic chart on the dashboard
-- ============================================================================
SELECT
    report_date,
    property_source,
    SUM(sessions)       AS total_sessions,
    SUM(total_users)    AS total_users,
    SUM(new_users)      AS total_new_users,
    SUM(pageviews)      AS total_pageviews,
    ROUND(AVG(avg_session_duration), 1) AS avg_duration_sec,
    ROUND(AVG(bounce_rate) * 100, 1)    AS bounce_rate_pct
FROM analytics.ga4_sessions
WHERE report_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY report_date, property_source
ORDER BY report_date, property_source;


-- ============================================================================
-- QUERY 5: Traffic by Channel Group (last 30 days)
-- Shows which channels drive the most traffic
-- ============================================================================
SELECT
    channel_group,
    property_source,
    SUM(sessions)    AS total_sessions,
    SUM(total_users) AS total_users,
    SUM(new_users)   AS total_new_users,
    ROUND(AVG(bounce_rate) * 100, 1) AS avg_bounce_pct
FROM analytics.ga4_sessions
WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY channel_group, property_source
ORDER BY total_sessions DESC;


-- ============================================================================
-- QUERY 6: Monthly Seasonal Trends (from materialized view)
-- Powers the seasonal heatmap / trend chart
-- ============================================================================
SELECT
    month,
    property_source,
    total_sessions,
    total_users,
    total_new_users,
    total_pageviews,
    avg_session_duration,
    ROUND(avg_bounce_rate * 100, 1) AS bounce_rate_pct,
    -- Month-over-month change
    ROUND(
        (total_sessions - LAG(total_sessions) OVER (
            PARTITION BY property_source ORDER BY month
        ))::NUMERIC /
        NULLIF(LAG(total_sessions) OVER (
            PARTITION BY property_source ORDER BY month
        ), 0) * 100,
        1
    ) AS mom_change_pct
FROM analytics.mv_monthly_traffic
ORDER BY month, property_source;


-- ============================================================================
-- QUERY 7: Cross-Property User Flow
-- Shows how many users visit both properties (requires custom_user_id)
-- ============================================================================
WITH main_users AS (
    SELECT DISTINCT custom_user_id
    FROM analytics.ga4_events
    WHERE property_source = 'main_website'
      AND custom_user_id IS NOT NULL
      AND report_date >= CURRENT_DATE - INTERVAL '30 days'
),
events_users AS (
    SELECT DISTINCT custom_user_id
    FROM analytics.ga4_events
    WHERE property_source = 'events_platform'
      AND custom_user_id IS NOT NULL
      AND report_date >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT
    (SELECT COUNT(*) FROM main_users)                                         AS main_site_users,
    (SELECT COUNT(*) FROM events_users)                                       AS events_platform_users,
    (SELECT COUNT(*) FROM main_users m JOIN events_users e USING (custom_user_id)) AS users_on_both,
    ROUND(
        (SELECT COUNT(*) FROM main_users m JOIN events_users e USING (custom_user_id))::NUMERIC /
        NULLIF((SELECT COUNT(*) FROM main_users), 0) * 100,
        1
    ) AS pct_main_users_also_on_events;


-- ============================================================================
-- QUERY 8: Funnel Validated Against Internal Registrations
-- Compares GA4 "complete_registration" events with actual DB registrations.
-- This catches tracking discrepancies (e.g. GA4 fires but DB insert fails,
-- or user registers without GA4 tracking).
-- NOTE: This is an aggregate comparison by date. For per-user matching,
-- the custom_user_id dimension must be configured in GA4.
-- ============================================================================
WITH ga4_counts AS (
    SELECT
        report_date,
        SUM(event_count) AS ga4_registrations
    FROM analytics.ga4_events
    WHERE event_name = 'complete_registration'
      AND report_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY report_date
),
db_counts AS (
    SELECT
        created_at::DATE AS registration_date,
        COUNT(*)         AS db_registrations
    FROM public.registrations
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY created_at::DATE
)
SELECT
    COALESCE(g.report_date, d.registration_date) AS report_date,
    COALESCE(g.ga4_registrations, 0)              AS ga4_registrations,
    COALESCE(d.db_registrations, 0)               AS db_registrations,
    COALESCE(g.ga4_registrations, 0) - COALESCE(d.db_registrations, 0) AS discrepancy
FROM ga4_counts g
FULL OUTER JOIN db_counts d ON g.report_date = d.registration_date
ORDER BY report_date;


-- ============================================================================
-- QUERY 9: Top Landing Pages (last 30 days)
-- Shows which pages attract the most first-time visitors
-- ============================================================================
SELECT
    page_path,
    property_source,
    SUM(sessions)    AS total_sessions,
    SUM(new_users)   AS new_users,
    ROUND(AVG(bounce_rate) * 100, 1) AS bounce_pct,
    ROUND(AVG(avg_session_duration), 0) AS avg_duration_sec
FROM analytics.ga4_sessions
WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY page_path, property_source
ORDER BY total_sessions DESC
LIMIT 20;


-- ============================================================================
-- QUERY 10: Device Breakdown (last 30 days)
-- ============================================================================
SELECT
    device_category,
    property_source,
    SUM(sessions)    AS total_sessions,
    SUM(total_users) AS total_users,
    ROUND(SUM(sessions)::NUMERIC /
        NULLIF(SUM(SUM(sessions)) OVER (PARTITION BY property_source), 0) * 100,
        1
    ) AS pct_of_traffic
FROM analytics.ga4_sessions
WHERE report_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY device_category, property_source
ORDER BY property_source, total_sessions DESC;


-- ============================================================================
-- QUERY 11: ETL Pipeline Health Check
-- Shows recent run status for monitoring
-- ============================================================================
SELECT
    id,
    run_started_at,
    run_ended_at,
    EXTRACT(EPOCH FROM (run_ended_at - run_started_at))::INTEGER AS duration_sec,
    target_date,
    property_source,
    rows_extracted,
    rows_loaded,
    status,
    LEFT(error_message, 100) AS error_preview
FROM analytics.etl_run_log
ORDER BY run_started_at DESC
LIMIT 20;
