-- 04_revenue_baseline.sql
-- Purpose : The untargeted baseline the model must beat - what ancillary revenue
--           looks like today, when the offer is shown to everyone at checkout.
--           The notebook's targeting simulation is measured against these numbers.
-- Dialect : Standard SQL (DuckDB-verified).

SELECT
  COUNT(*) AS bookings,
  SUM(purchased_ancillary) AS buyers,
  ROUND(AVG(purchased_ancillary) * 100, 2) AS take_rate_pct,
  SUM(ancillary_revenue_usd) AS total_ancillary_revenue_usd,
  ROUND(AVG(ancillary_revenue_usd), 2) AS revenue_per_booking_usd,
  ROUND(SUM(ancillary_revenue_usd) * 1.0 / SUM(purchased_ancillary), 2) AS revenue_per_buyer_usd,
  ROUND(SUM(bought_insurance * CASE WHEN route_type = 'International' THEN 32 ELSE 18 END) * 100.0
        / SUM(ancillary_revenue_usd), 1) AS insurance_share_of_revenue_pct,
  ROUND(SUM(bought_seat_upgrade * CASE WHEN route_type = 'International' THEN 60 ELSE 35 END) * 100.0
        / SUM(ancillary_revenue_usd), 1) AS seat_share_of_revenue_pct,
  ROUND(SUM(bought_extra_baggage * CASE WHEN route_type = 'International' THEN 40 ELSE 25 END) * 100.0
        / SUM(ancillary_revenue_usd), 1) AS baggage_share_of_revenue_pct
FROM bookings;
