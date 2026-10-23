"""Generate the synthetic flight-bookings + ancillary-purchase dataset.

WHY SYNTHETIC, STATED PLAINLY
------------------------------
Real ancillary-purchase data (who bought travel insurance, a seat upgrade or
extra baggage, and what they were shown at checkout) is not published by any
airline or OTA. This generator follows the same disclosure pattern as the
companion CTR project: bookings are simulated with realistic distributions,
and each ancillary purchase is drawn from an explicit, documented logistic
propensity model (below), so the signal the ML models later "find" is real,
recoverable and explainable - it is not random noise and it is not hidden.

PROPENSITY MODEL (log-odds, before the shared traveller trait)
--------------------------------------------------------------
insurance : -2.75 + 0.85*international + 0.40*has_children + 0.30*(party>=3)
            + 0.004*lead_time_days + 0.25*(fare>400) + 0.45*prior_ancillary_buyer
seat      : -2.95 + 0.16*duration_hrs + 0.55*business_purpose
            + 0.45*loyalty_silver_or_gold + 0.45*prior_ancillary_buyer
            (not offered in Business cabin - those passengers already have the seat)
baggage   : -2.35 + 0.50*(party>=3) + 0.40*has_children + 0.40*leisure
            + 0.30*international - 0.45*business_purpose + 0.45*prior_ancillary_buyer
plus a per-customer latent trait ~ N(0, 0.5) added to all three, which is what
creates repeat-buyer behaviour across a customer's bookings.

Prices (USD, by route type) - stated, not learned:
insurance 18 domestic / 32 international; seat upgrade 35 / 60; baggage 25 / 40.

Run:  python -m src.generate_data     (writes data/customers.csv, data/bookings.csv)
Seed: 42 everywhere. 60,000 bookings, 1 Jan - 29 Jun 2026 (rng.integers(0, 180)
excludes day 180). Both CSVs are written with LF line endings so regeneration is
byte-identical on every platform.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_BOOKINGS = 60_000
N_CUSTOMERS = 34_000
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

PRICES = {  # (domestic, international)
    "insurance": (18, 32),
    "seat_upgrade": (35, 60),
    "extra_baggage": (25, 40),
}
REGIONS = ["North America", "Europe", "South Asia", "Middle East", "East Asia", "Oceania"]


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def main() -> None:
    rng = np.random.default_rng(SEED)

    # ---------------- customers ----------------
    customers = pd.DataFrame({
        "customer_id": [f"C{ i:05d}" for i in range(1, N_CUSTOMERS + 1)],
        "home_region": rng.choice(REGIONS, N_CUSTOMERS, p=[.30, .24, .20, .10, .10, .06]),
        "loyalty_tier": rng.choice(["None", "Basic", "Silver", "Gold"], N_CUSTOMERS, p=[.55, .25, .13, .07]),
        "account_age_days": rng.integers(30, 2200, N_CUSTOMERS),
    })
    customers["traveller_trait"] = rng.normal(0, 0.5, N_CUSTOMERS)  # latent, NEVER a model feature

    # ---------------- bookings (checkout-time fields) ----------------
    cust = customers.sample(n=N_BOOKINGS, replace=True, random_state=SEED).reset_index(drop=True)
    international = rng.random(N_BOOKINGS) < 0.38
    duration = np.where(international, rng.uniform(3.5, 11.0, N_BOOKINGS), rng.uniform(0.8, 3.5, N_BOOKINGS))
    leisure = rng.random(N_BOOKINGS) < 0.71
    cabin = rng.choice(["Economy", "Premium Economy", "Business"], N_BOOKINGS, p=[.84, .09, .07])
    party = rng.choice([1, 2, 3, 4, 5], N_BOOKINGS, p=[.46, .33, .11, .07, .03])
    fare = np.round(rng.lognormal(mean=np.log(95 + 42 * duration) + np.where(cabin == "Business", 1.05,
                    np.where(cabin == "Premium Economy", 0.35, 0.0)), sigma=0.42, size=N_BOOKINGS), 2)

    bookings = pd.DataFrame({
        "booking_id": [f"B{ i:06d}" for i in range(1, N_BOOKINGS + 1)],
        "customer_id": cust["customer_id"].values,
        "booking_date": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 180, N_BOOKINGS), unit="D"),
        "route_type": np.where(international, "International", "Domestic"),
        "destination_region": rng.choice(REGIONS, N_BOOKINGS),
        "trip_purpose": np.where(leisure, "Leisure", "Business"),
        "cabin": cabin,
        "flight_duration_hrs": np.round(duration, 1),
        "lead_time_days": rng.integers(0, 181, N_BOOKINGS),
        "party_size": party,
        "has_children": (rng.random(N_BOOKINGS) < np.where(party >= 3, 0.52, 0.06)).astype(int),
        "fare_usd": fare,
        "channel": rng.choice(["Web", "App", "Agent"], N_BOOKINGS, p=[.55, .35, .10]),
        "device": rng.choice(["Mobile", "Desktop", "Tablet"], N_BOOKINGS, p=[.52, .41, .07]),
        "loyalty_tier": cust["loyalty_tier"].values,
        "_trait": cust["traveller_trait"].values,
    })
    bookings["departure_weekend"] = ((bookings["booking_date"].dt.day_of_week
                                      + bookings["lead_time_days"]) % 7 >= 5).astype(int)

    # history features + labels, in chronological order per customer
    bookings = bookings.sort_values(["customer_id", "booking_date", "booking_id"]).reset_index(drop=True)
    prior_trips = bookings.groupby("customer_id").cumcount()
    bookings["prior_trips"] = prior_trips

    intl = (bookings["route_type"] == "International").astype(int).values
    kids = bookings["has_children"].values
    big_party = (bookings["party_size"] >= 3).astype(int).values
    lead = bookings["lead_time_days"].values
    high_fare = (bookings["fare_usd"] > 400).astype(int).values
    biz = (bookings["trip_purpose"] == "Business").astype(int).values
    leis = 1 - biz
    silver_gold = bookings["loyalty_tier"].isin(["Silver", "Gold"]).astype(int).values
    trait = bookings["_trait"].values

    # Sequential draw in date order per customer, so the prior-buyer term in the
    # formulas uses only EARLIER bookings - the exact term stated in the docstring.
    dur = bookings["flight_duration_hrs"].values
    seat_offered = (bookings["cabin"] != "Business").values
    bought_ins = np.zeros(N_BOOKINGS, dtype=int)
    bought_seat = np.zeros(N_BOOKINGS, dtype=int)
    bought_bag = np.zeros(N_BOOKINGS, dtype=int)
    prior_buyer = np.zeros(N_BOOKINGS, dtype=int)
    seen_buyer: dict[str, int] = {}
    cust_ids = bookings["customer_id"].values
    for i in range(N_BOOKINGS):
        pb = seen_buyer.get(cust_ids[i], 0)
        prior_buyer[i] = pb
        p_ins = sigmoid(np.array([-2.75 + 0.85 * intl[i] + 0.40 * kids[i] + 0.30 * big_party[i]
                                  + 0.004 * lead[i] + 0.25 * high_fare[i] + 0.45 * pb + trait[i]]))[0]
        p_seat = sigmoid(np.array([-2.95 + 0.16 * dur[i] + 0.55 * biz[i] + 0.45 * silver_gold[i]
                                   + 0.45 * pb + trait[i]]))[0]
        p_bag = sigmoid(np.array([-2.35 + 0.50 * big_party[i] + 0.40 * kids[i] + 0.40 * leis[i]
                                  + 0.30 * intl[i] - 0.45 * biz[i] + 0.45 * pb + trait[i]]))[0]
        bought_ins[i] = int(rng.random() < p_ins)
        bought_seat[i] = int(seat_offered[i] and rng.random() < p_seat)
        bought_bag[i] = int(rng.random() < p_bag)
        if bought_ins[i] or bought_seat[i] or bought_bag[i]:
            seen_buyer[cust_ids[i]] = 1

    bookings["prior_ancillary_buyer"] = prior_buyer
    bookings["bought_insurance"] = bought_ins
    bookings["bought_seat_upgrade"] = bought_seat
    bookings["bought_extra_baggage"] = bought_bag
    bookings["purchased_ancillary"] = ((bought_ins + bought_seat + bought_bag) > 0).astype(int)

    price = lambda col, dom, intl_price: np.where(intl == 1, intl_price, dom)  # noqa: E731
    bookings["ancillary_revenue_usd"] = (
        bookings["bought_insurance"] * price("insurance", *PRICES["insurance"])
        + bookings["bought_seat_upgrade"] * price("seat", *PRICES["seat_upgrade"])
        + bookings["bought_extra_baggage"] * price("bag", *PRICES["extra_baggage"]))

    bookings = bookings.drop(columns=["_trait"])
    bookings = bookings.sort_values(["booking_date", "booking_id"]).reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers.drop(columns=["traveller_trait"]).to_csv(DATA_DIR / "customers.csv", index=False, lineterminator="\n")
    bookings.to_csv(DATA_DIR / "bookings.csv", index=False, lineterminator="\n")

    print(f"customers: {len(customers):,}  bookings: {len(bookings):,}")
    for c in ["bought_insurance", "bought_seat_upgrade", "bought_extra_baggage", "purchased_ancillary"]:
        print(f"  {c:24s} take rate {bookings[c].mean() * 100:5.2f}%")
    print(f"  ancillary revenue total  ${bookings['ancillary_revenue_usd'].sum():,.0f}"
          f"  (avg ${bookings['ancillary_revenue_usd'].mean():.2f}/booking)")


if __name__ == "__main__":
    main()
