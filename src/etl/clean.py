"""
Cleaning layer: applied after validation, before transformation. Handles the
kinds of imperfections a real raw log would have — duplicate rows, outlier
values, inconsistent categorical casing — even though the Phase 3 synthetic
generator produces clean data by construction. This stage exists so the
pipeline is honest about what a production ETL actually has to do, and so it
would keep working correctly if pointed at messier real data.
"""

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def clean_impressions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = df.copy()
    n_before = len(df)

    # Drop exact duplicate impression_id rows, keep first occurrence
    df = df.drop_duplicates(subset="impression_id", keep="first")
    n_after_dedup = len(df)
    if n_before != n_after_dedup:
        logger.info("  Dropped %s duplicate impression rows", n_before - n_after_dedup)

    # Cap floor_price_usd outliers rather than dropping rows — an
    # out-of-range floor price is a data-quality issue on one column, not a
    # reason to lose the rest of a real impression event.
    clean_cfg = config["cleaning"]
    lower, upper = clean_cfg["floor_price_lower_bound"], clean_cfg["floor_price_upper_bound"]
    n_capped = int(((df["floor_price_usd"] < lower) | (df["floor_price_usd"] > upper)).sum())
    df["floor_price_usd"] = df["floor_price_usd"].clip(lower=lower, upper=upper)
    if n_capped > 0:
        logger.info("  Capped %s floor_price_usd outliers to [%s, %s]", n_capped, lower, upper)

    # Normalize categorical text casing/whitespace defensively
    categorical_cols = [
        "device", "primary_device", "os", "browser", "ad_position", "country",
        "category", "objective", "target_device", "creative_type", "hour_bucket",
        "publisher_domain",
    ]
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    logger.info("  Cleaned impressions: %s -> %s rows", n_before, len(df))
    return df


def clean_clicks(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n_before = len(df)
    df = df.drop_duplicates(subset="click_id", keep="first")
    # A given impression should only be clicked once in this dataset design —
    # guard against any duplicate impression_id references in clicks.
    df = df.drop_duplicates(subset="impression_id", keep="first")
    df["click_timestamp"] = pd.to_datetime(df["click_timestamp"])
    if len(df) != n_before:
        logger.info("  Cleaned clicks: %s -> %s rows", n_before, len(df))
    return df
