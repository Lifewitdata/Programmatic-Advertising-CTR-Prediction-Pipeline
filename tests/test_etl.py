"""
Unit tests for the ETL pipeline. Run with: pytest tests/test_etl.py -v

These use small hand-built DataFrames rather than the full dataset, so they
run in milliseconds and pin down the exact edge-case behavior of each
validation/transform function.
"""

import pandas as pd
import pytest

from src.etl.validate import (
    _check_primary_key_uniqueness,
    _check_referential_integrity,
    _check_ctr_sanity,
    ValidationError,
)
from src.etl.transform import attach_label, time_based_split


def test_primary_key_uniqueness_passes_on_unique_ids():
    df = pd.DataFrame({"id": [1, 2, 3]})
    report = {}
    _check_primary_key_uniqueness(df, "id", "test_table", report)
    assert report["test_table.duplicate_pk_fraction"] == 0


def test_primary_key_uniqueness_raises_on_duplicates():
    df = pd.DataFrame({"id": [1, 2, 2]})
    report = {}
    with pytest.raises(ValidationError):
        _check_primary_key_uniqueness(df, "id", "test_table", report)


def test_referential_integrity_raises_on_orphan_rows():
    child = pd.DataFrame({"parent_id": [1, 2, 99]})
    parent = pd.DataFrame({"id": [1, 2, 3]})
    report = {}
    with pytest.raises(ValidationError):
        _check_referential_integrity(child, "parent_id", parent, "id", "child", "parent", report)


def test_ctr_sanity_raises_outside_bounds():
    impressions = pd.DataFrame({"impression_id": range(100)})
    clicks = pd.DataFrame({"click_id": range(50)})  # 50% CTR — clearly broken
    report = {}
    with pytest.raises(ValidationError):
        _check_ctr_sanity(impressions, clicks, report, min_ctr=0.001, max_ctr=0.2)


def test_attach_label_marks_clicked_impressions_correctly():
    impressions = pd.DataFrame({"impression_id": [1, 2, 3]})
    clicks = pd.DataFrame({"impression_id": [2], "click_timestamp": [pd.Timestamp("2025-10-01")]})
    result = attach_label(impressions, clicks)
    assert result.set_index("impression_id")["clicked"].to_dict() == {1: 0, 2: 1, 3: 0}
    assert "click_timestamp" not in result.columns


def test_time_based_split_has_no_temporal_overlap():
    df = pd.DataFrame({
        "impression_id": range(6),
        "timestamp": pd.to_datetime([
            "2025-11-01", "2025-11-15", "2025-12-05", "2025-12-10", "2025-12-20", "2025-12-25",
        ]),
        "clicked": [0, 1, 0, 1, 0, 1],
    })
    train, val, test = time_based_split(df, train_end_date="2025-11-30", val_end_date="2025-12-15")

    assert train["timestamp"].max() <= pd.Timestamp("2025-11-30")
    assert val["timestamp"].min() > pd.Timestamp("2025-11-30")
    assert val["timestamp"].max() <= pd.Timestamp("2025-12-15")
    assert test["timestamp"].min() > pd.Timestamp("2025-12-15")
    assert len(train) + len(val) + len(test) == len(df)
