-- 03_segment_take_rates.sql
-- Purpose : Ancillary take rates and revenue by the segments a Monetisation
--           team actually manages. Descriptive only - the model readout is the notebook.
-- Dialect : Standard SQL (DuckDB-verified).

-- By route type and trip purpose
SELECT route_type, trip_purpose,
       COUNT(*) AS bookings,
       ROUND(AVG(bought_insurance) * 100, 2) AS insurance_take_pct,
       ROUND(AVG(bought_seat_upgrade) * 100, 2) AS seat_take_pct,
       ROUND(AVG(bought_extra_baggage) * 100, 2) AS baggage_take_pct,
       ROUND(AVG(purchased_ancillary) * 100, 2) AS any_take_pct,
       ROUND(AVG(ancillary_revenue_usd), 2) AS revenue_per_booking
FROM bookings GROUP BY 1, 2 ORDER BY 1, 2;

-- By loyalty tier (does status predict add-on buying?)
SELECT loyalty_tier, COUNT(*) AS bookings,
       ROUND(AVG(purchased_ancillary) * 100, 2) AS any_take_pct,
       ROUND(AVG(ancillary_revenue_usd), 2) AS revenue_per_booking
FROM bookings GROUP BY 1 ORDER BY any_take_pct DESC;

-- Repeat behaviour: take rate by how many trips the customer had already taken
SELECT CASE WHEN prior_trips = 0 THEN '0 (first booking)'
            WHEN prior_trips = 1 THEN '1'
            WHEN prior_trips = 2 THEN '2'
            ELSE '3+' END AS prior_trips_band,
       COUNT(*) AS bookings,
       ROUND(AVG(purchased_ancillary) * 100, 2) AS any_take_pct,
       ROUND(AVG(prior_ancillary_buyer) * 100, 2) AS pct_who_bought_before
FROM bookings GROUP BY 1 ORDER BY MIN(prior_trips);
