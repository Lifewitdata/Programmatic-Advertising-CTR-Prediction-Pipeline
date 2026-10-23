# Ancillary Purchase Prediction & Revenue Optimization
## Will this booking buy an add-on at checkout — insurance, a seat upgrade, or extra baggage?

An end-to-end propensity model for a travel Monetisation team: predict, **at checkout and before the offer is shown**, the probability that a flight booking buys at least one ancillary; then use the ranked scores to simulate which targeting depth earns the most ancillary revenue per offer spent.

**Data disclosure:** real ancillary-purchase data is not published by any airline or OTA. This dataset (60,000 bookings, Jan–Jun 2026) is synthetic — bookings are simulated with realistic distributions and each purchase is drawn from an explicit, documented logistic propensity model (`src/generate_data.py`), so the signal is real and recoverable but no number here is a claim about a real airline. The workflow, leakage discipline, calibration practice and revenue method are the deliverable.

## Headline results

| | Value |
|---|---|
| Bookings / buyers | 60,000 / 23,224 (**38.71%** take rate) |
| Take rates by product | Insurance 17.07% · Extra baggage 16.52% · Seat upgrade 14.06% |
| Total ancillary revenue | **$990,235** ($16.50 per booking; seat upgrades are the largest share, 41.6%) |
| Split | Chronological: train Jan–Apr (40,011) · validation May (10,290) · test Jun (9,699) |
| **Logistic Regression (selected)** | Validation ROC-AUC **0.6515** · Test ROC-AUC **0.6565**, PR-AUC 0.5571 |
| Random Forest | Validation ROC-AUC 0.6501 · Test ROC-AUC 0.6554, PR-AUC 0.5562 |
| Calibration (selected, test) | Raw Brier **0.2236** — already calibrated (top score bin: predicted 0.662 vs actual 0.656); Platt scaling changed nothing (0.2237), so it was checked and *not* needed |
| Decile lift (test month) | Top decile take rate **65.57% = 1.61x** baseline (40.66%) |
| Revenue concentration | Top 30% of bookings hold **52.65%** of test-month ancillary revenue |
| Targeting efficiency | Net revenue per 1,000 offers at a $0.40/offer promo cost: top 30% = **$30,480** vs $17,197 offering to everyone (**+77%**) |

**The honest read on model selection:** the parametric model won, narrowly. The data-generating process is logistic, so Logistic Regression recovering it best is expected, not a surprise — and at this margin (0.001–0.004 AUC) the right claim is "no advantage to the more complex model here," not "Logistic Regression beats Random Forest." The strongest single predictor in both models is the same: **whether the customer has bought an ancillary before** (LR odds ratio 1.36; RF's largest permutation importance), then route type (international take rate ≈ 49.7% vs domestic ≈ 32%).

## Repository structure

```text
ancillary/
├── data/            customers.csv (34,000) + bookings.csv (60,000, with labels + revenue)
├── sql/             01 data quality - 02 analysis table (leakage-audited history)
│                    03 segment take rates - 04 untargeted revenue baseline
├── notebooks/       ancillary_propensity_model.ipynb - 45 cells, executed end to end
├── src/             generate_data.py - the documented propensity model + price list
├── reports/         model comparisons, decile lift, calibration (raw + Platt),
│                    targeting strategies, odds ratios, permutation importance
├── tableau/         4 connect-ready datasets (deciles, model comparison, segment take
│                    rates, calibration) - same shape the Part-1 workbook uses
├── tests/           6 pytest data-integrity tests (incl. SQL-vs-generated history proof)
├── requirements.txt
└── README.md
```

## How it works

1. **SQL data prep** (`sql/`): quality checks first (grain, label/revenue consistency, the no-seat-upgrades-in-Business rule — all return zero violations), then the analysis table: one row per booking with **only checkout-time fields**. Customer history (`prior_trips`, `prior_ancillary_buyer`) is recomputed in SQL from strictly earlier bookings — and a test proves the SQL and generated columns agree on all 60,000 rows.
2. **Leakage discipline:** the three `bought_*` flags are the outcome, `ancillary_revenue_usd` is post-decision, and the generator's latent traveller trait is never stored. Features = what is knowable before the offer renders.
3. **Models:** Logistic Regression (parametric — scaled numeric + one-hot, odds ratios reported) vs Random Forest (non-parametric — 300 trees, permutation importance). Selected on **validation** ROC-AUC; the test month is scored once.
4. **Calibration before revenue:** reliability table + Brier score on test, Platt scaling fitted on validation only. This is the step the companion CTR project failed (its predicted probabilities were 14–29x actual CTR by decile); here the check passes, which is exactly why the check exists.
5. **Revenue simulation** (`reports/targeting_strategies_test.csv`, Tableau datasets in `tableau/`): rank the test month by calibrated score, take cumulative revenue by targeting depth, and price the offer at a stated $0.40 promo cost per booking shown it. Totals always favour offering to everyone — a model cannot create buyers — so strategies are compared on **net revenue per 1,000 offers** and revenue share kept.

## Run it

```bash
pip install -r requirements.txt
python -m src.generate_data        # regenerates data/ byte-for-byte (seed 42)
pytest tests/ -q                   # 6 data-integrity tests
jupyter notebook notebooks/ancillary_propensity_model.ipynb   # run top to bottom
```

## Limitations — stated, not buried

- **Propensity is not uplift.** The model finds bookings likely to buy anyway; it does not prove the offer *caused* the purchase. The deployment-grade next step is an A/B test of the targeting strategy itself (targeted vs offer-to-everyone, revenue per booking as primary metric) or an uplift model. The section-14 simulation is an upper bound, not a measured increment.
- **Synthetic labels.** Segment effects and effect sizes are properties of the documented generation model.
- **One label quirk, stated:** `loyalty_tier` stores the literal string `None` for the 32,905 bookings whose customer has no programme tier, and pandas parses that as a null — so a naive groupby silently drops 55% of the bookings. The segment extract labels the group `No Tier` and its rows sum to all 60,000 bookings.
- **Visible drift:** the take rate climbs every month through the training window (36.2% Jan → 40.8% May) and then flattens (40.7% in Jun) as repeat buyers accumulate in the customer base — a production score needs scheduled retraining and calibration monitoring.
- Seat upgrades are not offered in Business cabin by construction (those passengers already hold the product); the model respects that rule in the data rather than learning around it.

## Part of Project 1

This folder is Part 2 of the repository's Project 1 (Ad-Targeting Optimization & Revenue Prediction): Part 1, in the repo root, predicts ad clicks on 1M impressions; this part applies the same method — Logistic Regression vs Random Forest, SQL data prep, calibrated probabilities, Tableau-ready revenue extracts — to ancillary purchases.
