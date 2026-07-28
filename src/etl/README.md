# ETL pipeline (Phase 5)

Run: `python -m src.etl.run_etl --config config/etl_config.yaml`
Test: `python -m pytest tests/test_etl.py -v`

## Stages
1. **extract** — pulls all 6 tables from PostgreSQL (falls back to
   `data/raw/*.csv` if the DB is unreachable, so the pipeline is runnable
   without standing up Postgres first)
2. **validate** — primary-key uniqueness, null checks, referential integrity
   (orphan FK detection), value-range checks, and an overall-CTR sanity check.
   Raises `ValidationError` and stops the pipeline on any failure — bad data
   never silently reaches training.
3. **clean** — deduplication, floor-price outlier capping, categorical
   normalization. A no-op on this synthetic data by construction, but keeps
   the pipeline correct if pointed at messier real data.
4. **transform** — LEFT JOINs clicks onto impressions to build the binary
   `clicked` label, then performs a **time-based** train/val/test split
   (not random) to avoid leaking future information into training.
5. **save** — writes `train.parquet`, `val.parquet`, `test.parquet`,
   `ctr_dataset_full.parquet`, and `validation_report.json`.

## Verified run (1M impressions)
- Extract: ~23s from Postgres
- Validation: all 17 checks passed
- Split: train 660,123 / val 164,223 / test 175,654 rows, CTR 2.29% / 2.20% /
  2.29% — consistent across the time split, confirming no drift artifact
  from the split boundaries themselves
- Total pipeline runtime: ~25s
