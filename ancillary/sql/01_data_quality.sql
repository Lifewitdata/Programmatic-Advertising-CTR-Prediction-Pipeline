-- 01_data_quality.sql
-- Purpose : Prove the bookings table is trustworthy before any model is trained.
-- Dialect : Standard SQL (executed and verified on DuckDB; PostgreSQL-compatible).
-- Tables  : bookings (60,000 rows), customers (34,000 rows) loaded from data/*.csv.

-- Check 1 - grain: one row per booking, one row per customer
SELECT 'bookings' AS table_name, COUNT(*) AS rows_, COUNT(DISTINCT booking_id) AS distinct_ids
FROM bookings
UNION ALL
SELECT 'customers', COUNT(*), COUNT(DISTINCT customer_id) FROM customers;

-- Check 2 - referential integrity: every booking belongs to a known customer (expected: 0 orphans)
SELECT COUNT(*) AS orphan_bookings
FROM bookings b LEFT JOIN customers c USING (customer_id)
WHERE c.customer_id IS NULL;

-- Check 3 - label consistency: purchased_ancillary must equal "any of the three products"
SELECT COUNT(*) AS inconsistent_labels   -- expected: 0
FROM bookings
WHERE purchased_ancillary != (CASE WHEN bought_insurance + bought_seat_upgrade + bought_extra_baggage > 0
                                  THEN 1 ELSE 0 END);

-- Check 4 - revenue consistency: revenue is 0 exactly when nothing was bought (expected: 0)
SELECT COUNT(*) AS revenue_mismatches
FROM bookings
WHERE (purchased_ancillary = 0 AND ancillary_revenue_usd != 0)
   OR (purchased_ancillary = 1 AND ancillary_revenue_usd <= 0);

-- Check 5 - business rule: seat upgrades are never sold into Business cabin (expected: 0)
SELECT COUNT(*) AS seat_sales_in_business_cabin
FROM bookings
WHERE cabin = 'Business' AND bought_seat_upgrade = 1;

-- Check 6 - null audit on model features and labels (expected: all 0)
SELECT
  COUNT_IF(fare_usd IS NULL) AS null_fare,
  COUNT_IF(lead_time_days IS NULL) AS null_lead_time,
  COUNT_IF(purchased_ancillary IS NULL) AS null_label
FROM bookings;
