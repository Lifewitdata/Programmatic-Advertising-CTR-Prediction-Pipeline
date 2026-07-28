"""
Applies sql/schema.sql, then bulk-loads all six CSVs from data/raw/ into
PostgreSQL using COPY (far faster than row-by-row INSERTs for a
million-row fact table). Load order respects foreign-key dependencies:

    users, advertisers  ->  campaigns  ->  creatives  ->  impressions  ->  clicks

Usage:
    python -m src.database.load_to_postgres
"""

import time
from pathlib import Path

import psycopg2

from src.database.db_config import DBConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# (csv filename, table name, ordered column list matching the CSV header)
LOAD_ORDER = [
    ("users.csv", "users",
     "user_id,country,primary_device,age_group,gender,primary_interest,"
     "n_interests,account_created_date,click_propensity"),
    ("advertisers.csv", "advertisers",
     "advertiser_id,advertiser_name,industry,hq_country"),
    ("campaigns.csv", "campaigns",
     "campaign_id,advertiser_id,category,objective,target_country,target_device,"
     "start_date,end_date,daily_budget_usd,total_budget_usd,bid_strategy"),
    ("creatives.csv", "creatives",
     "creative_id,campaign_id,creative_type,size,headline"),
    ("impressions.csv", "impressions",
     "impression_id,\"timestamp\",user_id,campaign_id,ad_position,browser,"
     "publisher_domain,floor_price_usd,country,primary_device,device,os,"
     "advertiser_id,category,objective,target_device,creative_id,creative_type,"
     "hour_of_day,day_of_week,is_weekend,\"date\",hour_bucket,prior_impressions_today"),
    ("clicks.csv", "clicks",
     "click_id,impression_id,click_timestamp"),
]


def apply_schema(conn, schema_path: str = "sql/schema.sql") -> None:
    logger.info("Applying schema from %s", schema_path)
    sql = Path(schema_path).read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info("Schema applied.")


def load_csv(conn, csv_path: Path, table: str, columns: str) -> int:
    with conn.cursor() as cur:
        with open(csv_path, "r") as f:
            copy_sql = f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            cur.copy_expert(copy_sql, f)
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
    conn.commit()
    return row_count


def main(data_dir: str = "data/raw") -> None:
    t0 = time.time()
    db_config = DBConfig()
    conn = psycopg2.connect(db_config.dsn)

    try:
        apply_schema(conn)

        data_path = Path(data_dir)
        for filename, table, columns in LOAD_ORDER:
            file_path = data_path / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Expected {file_path} — run Phase 3 data generation first.")

            t_start = time.time()
            row_count = load_csv(conn, file_path, table, columns)
            logger.info(
                "Loaded %s -> %s: %s rows in %.1fs",
                filename, table, row_count, time.time() - t_start,
            )

        logger.info("All tables loaded in %.1fs", time.time() - t0)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
