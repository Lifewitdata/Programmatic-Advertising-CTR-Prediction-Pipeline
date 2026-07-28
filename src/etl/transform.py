"""
Transformation layer: joins the cleaned impressions with clicks to attach the
binary `clicked` label, then produces a time-based train/validation/test
split.

The label join is a LEFT JOIN, not an INNER JOIN — every impression belongs
in the dataset whether or not it was clicked, since "not clicked" is the
majority class we're modeling, not a row to discard.
"""

from typing import Tuple

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def attach_label(impressions: pd.DataFrame, clicks: pd.DataFrame) -> pd.DataFrame:
    df = impressions.merge(
        clicks[["impression_id", "click_timestamp"]], on="impression_id", how="left"
    )
    df["clicked"] = df["click_timestamp"].notna().astype(int)
    df = df.drop(columns=["click_timestamp"])  # not usable as a prediction-time feature

    ctr = df["clicked"].mean()
    logger.info("Attached labels. Dataset CTR: %.4f%% (%s / %s)", ctr * 100, df["clicked"].sum(), len(df))
    return df


def time_based_split(
    df: pd.DataFrame, train_end_date: str, val_end_date: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split chronologically: train on the past, validate and test on
    progressively later windows. This matches how the model will actually be
    evaluated in production (score requests that happen after training data
    was collected) and avoids the leakage a random split would introduce via
    campaign- and user-level statistics computed in Phase 7.
    """
    train_end = pd.Timestamp(train_end_date)
    val_end = pd.Timestamp(val_end_date)

    train = df[df["timestamp"] <= train_end].copy()
    val = df[(df["timestamp"] > train_end) & (df["timestamp"] <= val_end)].copy()
    test = df[df["timestamp"] > val_end].copy()

    for name, split_df in [("train", train), ("val", val), ("test", test)]:
        ctr = split_df["clicked"].mean() if len(split_df) else float("nan")
        logger.info(
            "  %s: %s rows, %s to %s, CTR %.4f%%",
            name, len(split_df),
            split_df["timestamp"].min(), split_df["timestamp"].max(),
            ctr * 100,
        )

    return train, val, test
