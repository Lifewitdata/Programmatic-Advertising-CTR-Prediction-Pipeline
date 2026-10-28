-- Run as the database owner in a dedicated DEMO database, after schema.sql.
-- These NOLOGIN roles demonstrate isolation. Real login provisioning is separate.
CREATE SCHEMA IF NOT EXISTS ctr_reporting;
CREATE TABLE IF NOT EXISTS ctr_reporting.campaign_daily (
    event_date DATE NOT NULL,
    advertiser_id BIGINT NOT NULL,
    campaign_id BIGINT NOT NULL,
    device TEXT NOT NULL,
    country TEXT NOT NULL,
    impressions BIGINT NOT NULL CHECK (impressions > 0),
    clicks BIGINT NOT NULL CHECK (clicks >= 0 AND clicks <= impressions),
    PRIMARY KEY (event_date, advertiser_id, campaign_id, device, country)
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='advertiser_1') THEN
        CREATE ROLE advertiser_1 NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='advertiser_2') THEN
        CREATE ROLE advertiser_2 NOLOGIN;
    END IF;
END $$;
ALTER TABLE ctr_reporting.campaign_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE ctr_reporting.campaign_daily FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS advertiser_isolation ON ctr_reporting.campaign_daily;
CREATE POLICY advertiser_isolation ON ctr_reporting.campaign_daily
    FOR SELECT TO advertiser_1, advertiser_2
    USING (advertiser_id = substring(current_user::text FROM '^advertiser_([0-9]+)$')::bigint);
REVOKE ALL ON SCHEMA ctr_reporting FROM PUBLIC;
REVOKE ALL ON ctr_reporting.campaign_daily FROM PUBLIC;
GRANT USAGE ON SCHEMA ctr_reporting TO advertiser_1, advertiser_2;
GRANT SELECT ON ctr_reporting.campaign_daily TO advertiser_1, advertiser_2;
-- Reporting roles receive no access to public.users, impressions, or clicks.
-- Table owners/superusers remain trusted administrators, not tenant identities.
