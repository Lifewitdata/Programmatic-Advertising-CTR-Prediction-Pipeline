"""Data-integrity tests for the ancillary purchase dataset.

Run:  pytest tests/ -q
Covers the same checks as sql/01_data_quality.sql plus the leakage-critical
history recomputation in sql/02_analysis_table.sql.
"""
from pathlib import Path

import duckdb
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"


def load():
    bookings = pd.read_csv(DATA / "bookings.csv", parse_dates=["booking_date"])
    customers = pd.read_csv(DATA / "customers.csv")
    return bookings, customers


def test_grain():
    b, c = load()
    assert b["booking_id"].is_unique and len(b) == 60_000
    assert c["customer_id"].is_unique and len(c) == 34_000


def test_no_orphan_customers():
    b, c = load()
    assert b["customer_id"].isin(c["customer_id"]).all()


def test_label_consistency():
    b, _ = load()
    any_bought = (b[["bought_insurance", "bought_seat_upgrade", "bought_extra_baggage"]].sum(axis=1) > 0).astype(int)
    assert (b["purchased_ancillary"] == any_bought).all()
    assert (((b["purchased_ancillary"] == 0) & (b["ancillary_revenue_usd"] == 0)) |
            ((b["purchased_ancillary"] == 1) & (b["ancillary_revenue_usd"] > 0))).all()


def test_business_rule_seat_not_in_business_cabin():
    b, _ = load()
    assert not ((b["cabin"] == "Business") & (b["bought_seat_upgrade"] == 1)).any()


def test_history_columns_are_leakage_safe():
    """prior_* must be computable from strictly earlier bookings of the same customer."""
    b, _ = load()
    b = b.sort_values(["customer_id", "booking_date", "booking_id"])
    prior_trips = b.groupby("customer_id").cumcount()
    prior_buyer = (b.groupby("customer_id")["purchased_ancillary"].cumsum() - b["purchased_ancillary"]).clip(upper=1)
    assert (b["prior_trips"] == prior_trips).all()
    assert (b["prior_ancillary_buyer"] == prior_buyer.astype(int)).all()


def test_sql_history_matches_generated():
    con = duckdb.connect()
    root = Path(__file__).resolve().parents[1]
    con.execute(f"CREATE VIEW bookings AS SELECT * FROM read_csv_auto('{(root / 'data' / 'bookings.csv').as_posix()}')")
    con.execute(f"CREATE VIEW customers AS SELECT * FROM read_csv_auto('{(root / 'data' / 'customers.csv').as_posix()}')")
    sql = (root / "sql" / "02_analysis_table.sql").read_text()
    body = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    create = body.split(";")[0]
    con.execute(create)
    mismatches = con.execute(
        "SELECT COUNT(*) FROM booking_analysis ba JOIN bookings b USING (booking_id) "
        "WHERE ba.prior_trips != b.prior_trips OR ba.prior_ancillary_buyer != b.prior_ancillary_buyer"
    ).fetchone()[0]
    assert mismatches == 0
