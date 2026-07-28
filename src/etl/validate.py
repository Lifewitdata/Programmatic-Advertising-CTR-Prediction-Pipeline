"""
Validation layer: runs a battery of checks on the raw extracted tables
before anything is cleaned or transformed. Fails loudly (raises) on checks
that would silently corrupt the model dataset if ignored — missing FK
references, duplicate primary keys — and logs warnings for checks that are
informative but not fatal.

Produces a JSON-serializable report so a run's validation results can be
saved alongside the processed data for auditability.
"""

from typing import Dict

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when a critical data-quality check fails."""


def _check_primary_key_uniqueness(df: pd.DataFrame, key: str, table: str, report: dict) -> None:
    n_total = len(df)
    n_unique = df[key].nunique()
    duplicate_fraction = 1 - (n_unique / n_total) if n_total else 0
    report[f"{table}.duplicate_pk_fraction"] = duplicate_fraction
    if duplicate_fraction > 0:
        raise ValidationError(
            f"{table}.{key} has {n_total - n_unique} duplicate values "
            f"({duplicate_fraction:.6f} of rows)."
        )
    logger.info("  [OK] %s.%s is unique (%s rows)", table, key, n_total)


def _check_no_nulls(df: pd.DataFrame, columns: list, table: str, report: dict, max_fraction: float) -> None:
    for col in columns:
        null_fraction = df[col].isna().mean()
        report[f"{table}.{col}.null_fraction"] = null_fraction
        if null_fraction > max_fraction:
            raise ValidationError(
                f"{table}.{col} has {null_fraction:.4%} nulls, exceeding max allowed {max_fraction:.4%}."
            )
    logger.info("  [OK] %s null checks passed for %s columns", table, len(columns))


def _check_referential_integrity(
    child_df: pd.DataFrame, child_key: str, parent_df: pd.DataFrame, parent_key: str,
    child_table: str, parent_table: str, report: dict,
) -> None:
    orphan_mask = ~child_df[child_key].isin(parent_df[parent_key])
    n_orphans = int(orphan_mask.sum())
    report[f"{child_table}.{child_key}_orphans"] = n_orphans
    if n_orphans > 0:
        raise ValidationError(
            f"{child_table}.{child_key} has {n_orphans} rows referencing "
            f"missing {parent_table}.{parent_key}."
        )
    logger.info("  [OK] %s.%s -> %s.%s referential integrity holds", child_table, child_key, parent_table, parent_key)


def _check_ctr_sanity(impressions: pd.DataFrame, clicks: pd.DataFrame, report: dict, min_ctr: float, max_ctr: float) -> None:
    ctr = len(clicks) / len(impressions)
    report["overall_ctr"] = ctr
    if not (min_ctr <= ctr <= max_ctr):
        raise ValidationError(
            f"Overall CTR {ctr:.4%} is outside the sane range [{min_ctr:.2%}, {max_ctr:.2%}] "
            f"— likely a broken join or generator bug, not real signal."
        )
    logger.info("  [OK] Overall CTR %.4f%% within sane range", ctr * 100)


def _check_value_ranges(df: pd.DataFrame, table: str, report: dict) -> None:
    checks_passed = 0
    if "hour_of_day" in df.columns:
        bad = ((df["hour_of_day"] < 0) | (df["hour_of_day"] > 23)).sum()
        report[f"{table}.hour_of_day_out_of_range"] = int(bad)
        if bad > 0:
            raise ValidationError(f"{table}.hour_of_day has {bad} values outside [0, 23].")
        checks_passed += 1
    if "floor_price_usd" in df.columns:
        bad = (df["floor_price_usd"] < 0).sum()
        report[f"{table}.negative_floor_price"] = int(bad)
        if bad > 0:
            raise ValidationError(f"{table}.floor_price_usd has {bad} negative values.")
        checks_passed += 1
    logger.info("  [OK] %s value-range checks passed (%s checks)", table, checks_passed)


def validate(data: Dict[str, pd.DataFrame], config: dict) -> dict:
    """Run the full validation suite. Returns a report dict.

    Raises ValidationError on the first critical failure — an ETL pipeline
    should stop, not silently propagate bad data into model training.
    """
    v_cfg = config["validation"]
    report: dict = {}

    logger.info("Running validation suite...")

    _check_primary_key_uniqueness(data["users"], "user_id", "users", report)
    _check_primary_key_uniqueness(data["advertisers"], "advertiser_id", "advertisers", report)
    _check_primary_key_uniqueness(data["campaigns"], "campaign_id", "campaigns", report)
    _check_primary_key_uniqueness(data["creatives"], "creative_id", "creatives", report)
    _check_primary_key_uniqueness(data["impressions"], "impression_id", "impressions", report)
    _check_primary_key_uniqueness(data["clicks"], "click_id", "clicks", report)

    _check_no_nulls(
        data["impressions"],
        ["user_id", "campaign_id", "creative_id", "timestamp", "device", "country"],
        "impressions", report, v_cfg["max_null_fraction"],
    )

    _check_referential_integrity(
        data["impressions"], "user_id", data["users"], "user_id",
        "impressions", "users", report,
    )
    _check_referential_integrity(
        data["impressions"], "campaign_id", data["campaigns"], "campaign_id",
        "impressions", "campaigns", report,
    )
    _check_referential_integrity(
        data["clicks"], "impression_id", data["impressions"], "impression_id",
        "clicks", "impressions", report,
    )

    _check_value_ranges(data["impressions"], "impressions", report)

    _check_ctr_sanity(
        data["impressions"], data["clicks"], report,
        v_cfg["min_ctr"], v_cfg["max_ctr"],
    )

    logger.info("All validation checks passed.")
    return report
