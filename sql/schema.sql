-- =============================================================================
-- CTR Prediction Platform — PostgreSQL Schema
-- Phase 4: Database Design
-- =============================================================================
-- Design notes:
--  - Star-ish schema: advertisers -> campaigns -> creatives feed impressions,
--    users feed impressions, clicks references impressions 1:1 (a click can
--    only happen against an impression that occurred).
--  - impressions is the fact table (millions of rows); everything else is
--    dimension/reference data.
--  - Indexes are added deliberately on FK columns and on columns used in the
--    CTR analysis queries below (campaign_id, country, device, timestamp),
--    not blanket-indexed on every column, to keep write/load performance
--    reasonable on a fact table this size.
-- =============================================================================

DROP TABLE IF EXISTS clicks CASCADE;
DROP TABLE IF EXISTS impressions CASCADE;
DROP TABLE IF EXISTS creatives CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS advertisers CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- -----------------------------------------------------------------------------
-- Dimension: users
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    user_id               BIGINT PRIMARY KEY,
    country               VARCHAR(2)   NOT NULL,
    primary_device        VARCHAR(20)  NOT NULL,
    age_group             VARCHAR(10)  NOT NULL,
    gender                VARCHAR(10)  NOT NULL,
    primary_interest      VARCHAR(30)  NOT NULL,
    n_interests           SMALLINT     NOT NULL CHECK (n_interests > 0),
    account_created_date  DATE         NOT NULL,
    click_propensity      NUMERIC(6,4) NOT NULL
);

-- -----------------------------------------------------------------------------
-- Dimension: advertisers
-- -----------------------------------------------------------------------------
CREATE TABLE advertisers (
    advertiser_id    BIGINT PRIMARY KEY,
    advertiser_name  VARCHAR(100) NOT NULL,
    industry         VARCHAR(30)  NOT NULL,
    hq_country       VARCHAR(2)   NOT NULL
);

-- -----------------------------------------------------------------------------
-- Dimension: campaigns (child of advertisers)
-- -----------------------------------------------------------------------------
CREATE TABLE campaigns (
    campaign_id       BIGINT PRIMARY KEY,
    advertiser_id     BIGINT       NOT NULL REFERENCES advertisers(advertiser_id),
    category          VARCHAR(30)  NOT NULL,
    objective         VARCHAR(20)  NOT NULL,
    target_country    VARCHAR(2)   NOT NULL,
    target_device     VARCHAR(20)  NOT NULL,
    start_date        DATE         NOT NULL,
    end_date          DATE         NOT NULL CHECK (end_date >= start_date),
    daily_budget_usd  NUMERIC(10,2) NOT NULL CHECK (daily_budget_usd > 0),
    total_budget_usd  NUMERIC(12,2) NOT NULL CHECK (total_budget_usd > 0),
    bid_strategy      VARCHAR(20)  NOT NULL
);

CREATE INDEX idx_campaigns_advertiser_id ON campaigns(advertiser_id);

-- -----------------------------------------------------------------------------
-- Dimension: creatives (child of campaigns)
-- -----------------------------------------------------------------------------
CREATE TABLE creatives (
    creative_id     BIGINT PRIMARY KEY,
    campaign_id     BIGINT      NOT NULL REFERENCES campaigns(campaign_id),
    creative_type   VARCHAR(20) NOT NULL,
    size            VARCHAR(20) NOT NULL,
    headline        VARCHAR(100) NOT NULL
);

CREATE INDEX idx_creatives_campaign_id ON creatives(campaign_id);

-- -----------------------------------------------------------------------------
-- Fact table: impressions (millions of rows)
-- -----------------------------------------------------------------------------
CREATE TABLE impressions (
    impression_id             BIGINT PRIMARY KEY,
    "timestamp"                TIMESTAMP    NOT NULL,
    user_id                    BIGINT       NOT NULL REFERENCES users(user_id),
    campaign_id                BIGINT       NOT NULL REFERENCES campaigns(campaign_id),
    ad_position                VARCHAR(20)  NOT NULL,
    browser                    VARCHAR(30)  NOT NULL,
    publisher_domain           VARCHAR(100) NOT NULL,
    floor_price_usd            NUMERIC(6,3) NOT NULL,
    country                    VARCHAR(2)   NOT NULL,
    primary_device              VARCHAR(20)  NOT NULL,
    device                      VARCHAR(20)  NOT NULL,
    os                          VARCHAR(20)  NOT NULL,
    advertiser_id               BIGINT       NOT NULL REFERENCES advertisers(advertiser_id),
    category                    VARCHAR(30)  NOT NULL,
    objective                   VARCHAR(20)  NOT NULL,
    target_device                VARCHAR(20)  NOT NULL,
    creative_id                  BIGINT       NOT NULL REFERENCES creatives(creative_id),
    creative_type                 VARCHAR(20)  NOT NULL,
    hour_of_day                   SMALLINT     NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week                   SMALLINT     NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    is_weekend                    BOOLEAN      NOT NULL,
    "date"                          DATE         NOT NULL,
    hour_bucket                    VARCHAR(20)  NOT NULL,
    prior_impressions_today        SMALLINT     NOT NULL
);

-- Indexes matched to the analysis queries below and to expected ETL access
-- patterns (filter/join by campaign, country, device, and time window).
CREATE INDEX idx_impressions_campaign_id ON impressions(campaign_id);
CREATE INDEX idx_impressions_user_id ON impressions(user_id);
CREATE INDEX idx_impressions_timestamp ON impressions("timestamp");
CREATE INDEX idx_impressions_country ON impressions(country);
CREATE INDEX idx_impressions_device ON impressions(device);
CREATE INDEX idx_impressions_date ON impressions("date");

-- -----------------------------------------------------------------------------
-- Fact table: clicks (subset of impressions — sparse, ~1-3% of impressions)
-- -----------------------------------------------------------------------------
CREATE TABLE clicks (
    click_id         BIGINT PRIMARY KEY,
    impression_id    BIGINT    NOT NULL UNIQUE REFERENCES impressions(impression_id),
    click_timestamp  TIMESTAMP NOT NULL
);

CREATE INDEX idx_clicks_impression_id ON clicks(impression_id);
