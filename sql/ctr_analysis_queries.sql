-- =============================================================================
-- CTR Prediction Platform — CTR Analysis Queries
-- Phase 4: Database Design
-- =============================================================================
-- All queries run against the schema in sql/schema.sql. Every query computes
-- CTR as clicks / impressions using a LEFT JOIN against clicks (impressions
-- without a matching click are still counted in the denominator) rather than
-- an INNER JOIN, which would silently drop non-clicked impressions and
-- inflate CTR. This is the single most common CTR-SQL correctness bug.

-- -----------------------------------------------------------------------------
-- 1. CTR by campaign, joined up to advertiser name, ranked
-- -----------------------------------------------------------------------------
SELECT
    c.campaign_id,
    a.advertiser_name,
    c.category,
    c.objective,
    COUNT(i.impression_id)                                   AS impressions,
    COUNT(cl.click_id)                                        AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct,
    RANK() OVER (ORDER BY COUNT(cl.click_id)::NUMERIC / COUNT(i.impression_id) DESC) AS ctr_rank
FROM impressions i
JOIN campaigns c    ON c.campaign_id = i.campaign_id
JOIN advertisers a  ON a.advertiser_id = c.advertiser_id
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY c.campaign_id, a.advertiser_name, c.category, c.objective
HAVING COUNT(i.impression_id) >= 500          -- exclude low-volume campaigns from the ranking
ORDER BY ctr_pct DESC
LIMIT 15;

-- -----------------------------------------------------------------------------
-- 2. CTR by country
-- -----------------------------------------------------------------------------
SELECT
    i.country,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY i.country
ORDER BY ctr_pct DESC;

-- -----------------------------------------------------------------------------
-- 3. CTR by device
-- -----------------------------------------------------------------------------
SELECT
    i.device,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY i.device
ORDER BY ctr_pct DESC;

-- -----------------------------------------------------------------------------
-- 4. CTR by browser
-- -----------------------------------------------------------------------------
SELECT
    i.browser,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY i.browser
ORDER BY ctr_pct DESC;

-- -----------------------------------------------------------------------------
-- 5. CTR by hour of day (time-of-day pattern)
-- -----------------------------------------------------------------------------
SELECT
    i.hour_of_day,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY i.hour_of_day
ORDER BY i.hour_of_day;

-- -----------------------------------------------------------------------------
-- 6. Daily CTR trend with a 7-day moving average (window function)
-- -----------------------------------------------------------------------------
WITH daily AS (
    SELECT
        i."date",
        COUNT(i.impression_id) AS impressions,
        COUNT(cl.click_id)      AS clicks
    FROM impressions i
    LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
    GROUP BY i."date"
)
SELECT
    "date",
    impressions,
    clicks,
    ROUND(100.0 * clicks / impressions, 4) AS ctr_pct,
    ROUND(
        AVG(100.0 * clicks / impressions) OVER (
            ORDER BY "date" ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 4
    ) AS ctr_7day_moving_avg
FROM daily
ORDER BY "date";

-- -----------------------------------------------------------------------------
-- 7. CTR by device x creative_type (two-dimensional cross-tab via GROUPING SETS)
-- -----------------------------------------------------------------------------
SELECT
    i.device,
    i.creative_type,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY GROUPING SETS ((i.device, i.creative_type), (i.device), ())
ORDER BY i.device NULLS LAST, i.creative_type NULLS LAST;

-- -----------------------------------------------------------------------------
-- 8. Top publisher domains by CTR, with a minimum volume threshold
-- -----------------------------------------------------------------------------
SELECT
    i.publisher_domain,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY i.publisher_domain
HAVING COUNT(i.impression_id) >= 1000
ORDER BY ctr_pct DESC;

-- -----------------------------------------------------------------------------
-- 9. Fatigue curve: CTR vs. same-day prior impressions per user
-- -----------------------------------------------------------------------------
SELECT
    LEAST(i.prior_impressions_today, 5) AS prior_impressions_bucket,
    COUNT(i.impression_id)                                    AS impressions,
    COUNT(cl.click_id)                                         AS clicks,
    ROUND(100.0 * COUNT(cl.click_id) / COUNT(i.impression_id), 4) AS ctr_pct
FROM impressions i
LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
GROUP BY LEAST(i.prior_impressions_today, 5)
ORDER BY prior_impressions_bucket;

-- -----------------------------------------------------------------------------
-- 10. Advertiser-level rollup: campaigns, spend proxy, and blended CTR,
--     with each campaign's CTR rank *within* its own advertiser (window fn)
-- -----------------------------------------------------------------------------
WITH campaign_ctr AS (
    SELECT
        c.advertiser_id,
        c.campaign_id,
        COUNT(i.impression_id) AS impressions,
        COUNT(cl.click_id)      AS clicks
    FROM impressions i
    JOIN campaigns c    ON c.campaign_id = i.campaign_id
    LEFT JOIN clicks cl ON cl.impression_id = i.impression_id
    GROUP BY c.advertiser_id, c.campaign_id
)
SELECT
    a.advertiser_name,
    cc.campaign_id,
    cc.impressions,
    cc.clicks,
    ROUND(100.0 * cc.clicks / NULLIF(cc.impressions, 0), 4) AS campaign_ctr_pct,
    ROUND(
        100.0 * SUM(cc.clicks) OVER (PARTITION BY cc.advertiser_id)
        / NULLIF(SUM(cc.impressions) OVER (PARTITION BY cc.advertiser_id), 0), 4
    ) AS advertiser_blended_ctr_pct,
    RANK() OVER (
        PARTITION BY cc.advertiser_id ORDER BY cc.clicks::NUMERIC / NULLIF(cc.impressions, 0) DESC
    ) AS rank_within_advertiser
FROM campaign_ctr cc
JOIN advertisers a ON a.advertiser_id = cc.advertiser_id
WHERE cc.impressions >= 300
ORDER BY a.advertiser_name, rank_within_advertiser
LIMIT 30;
