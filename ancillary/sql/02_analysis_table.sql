-- 02_analysis_table.sql
-- Purpose : Build the modelling table - one row per booking, ONLY the fields known
--           at checkout BEFORE the ancillary offer is shown, plus the label.
-- Leakage audit (read this before adding a column):
--   EXCLUDED on purpose: ancillary_revenue_usd and the three bought_* flags are
--   outcomes, not features. Nothing recorded after the purchase decision may
--   enter this table as a predictor. prior_* history is recomputed here from
--   earlier bookings only (window over the customer's own past), and a test in
--   tests/ proves it matches the generated columns exactly.
-- Dialect : Standard SQL (DuckDB-verified; PostgreSQL-compatible window functions).

CREATE OR REPLACE VIEW booking_analysis AS
WITH ordered AS (
  SELECT
    b.*,
    ROW_NUMBER() OVER (PARTITION BY b.customer_id ORDER BY b.booking_date, b.booking_id) AS cust_booking_seq
  FROM bookings b
),
history AS (
  SELECT
    booking_id,
    cust_booking_seq - 1 AS prior_trips_sql,
    MAX(purchased_ancillary) OVER (
      PARTITION BY customer_id ORDER BY booking_date, booking_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_buyer_sql
  FROM ordered
)
SELECT
  b.booking_id, b.customer_id, b.booking_date,
  b.route_type, b.destination_region, b.trip_purpose, b.cabin,
  b.flight_duration_hrs, b.lead_time_days, b.party_size, b.has_children,
  b.fare_usd, b.channel, b.device, b.loyalty_tier, b.departure_weekend,
  h.prior_trips_sql AS prior_trips,
  COALESCE(h.prior_buyer_sql, 0) AS prior_ancillary_buyer,
  b.purchased_ancillary AS label
FROM bookings b
JOIN history h USING (booking_id);

-- Sanity read: take rate by month (the chronological split the model uses)
SELECT
  DATE_TRUNC('month', booking_date) AS booking_month,
  COUNT(*) AS bookings,
  ROUND(AVG(purchased_ancillary) * 100, 2) AS ancillary_take_rate_pct,
  ROUND(SUM(ancillary_revenue_usd), 0) AS ancillary_revenue_usd
FROM bookings
GROUP BY 1 ORDER BY 1;
