"""
Applies sql/schema.sql, then bulk-loads all six CSVs from data/raw/ into
PostgreSQL using COPY (far faster than row-by-row INSERTs for a
million-row fact table). Load order respects foreign-key dependencies:

    users, advertisers  ->  campaigns  ->  creatives  ->  impressions  ->  clicks

Usage:
    python -m src.database.load_to_postgres
"""

import argparse
import io
import pandas as pd
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
    logger.info("Schema applied.")


def load_csv(conn, csv_path: Path, table: str, columns: str) -> int:
    with conn.cursor() as cur:
        ordered = [name.strip('"') for name in columns.split(',')]
        # COPY maps positional values, not CSV header names. Reorder explicitly
        # so valid input files need not share the schema's physical column order.
        for chunk in pd.read_csv(csv_path, chunksize=100000):
            if set(ordered) - set(chunk.columns):
                raise ValueError(f'Missing required CSV columns for {table}')
            buffer = io.StringIO()
            chunk[ordered].to_csv(buffer, index=False)
            buffer.seek(0)
            copy_sql = f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            cur.copy_expert(copy_sql, buffer)
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
    return row_count


def main(data_dir: str = "data/raw", replace_demo_data: bool = False) -> None:
    t0 = time.time()
    db_config = DBConfig()
    conn = psycopg2.connect(db_config.dsn)

    try:
        apply_schema(conn)
        with conn.cursor() as cur:
            for _, table, _ in LOAD_ORDER:
                cur.execute(f'SELECT EXISTS (SELECT 1 FROM {table})')
                if cur.fetchone()[0] and not replace_demo_data:
                    raise ValueError('Demo tables contain data; use --replace-demo-data for an intentional rebuild')
            cur.execute('TRUNCATE clicks, impressions, creatives, campaigns, advertisers, users')

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

        conn.commit()
        logger.info("All tables loaded in %.1fs", time.time() - t0)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='data/raw')
    parser.add_argument('--replace-demo-data', action='store_true')
    args = parser.parse_args()
    main(args.data_dir, args.replace_demo_data)

