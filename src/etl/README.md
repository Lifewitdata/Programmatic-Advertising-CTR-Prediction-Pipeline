# Data preparation

Use `python -m src.run_pipeline --n-impressions 25000` for the complete current
workflow. It generates inputs, validates contracts, attributes clicks within
24 hours, waits for fully observed labels, builds point-in-time features and
produces reconciled reports. The explicit CSV path is the default.

`python -m src.etl.run_etl` is a lower-level preparation entry point for supplied
CSV or PostgreSQL inputs and requires the matching raw observation manifest.
PostgreSQL is never silently replaced by CSV on failure. Duplicate keys and
broken relationships fail before transformation.

`load_to_postgres` loads all six raw tables in one transaction. A fresh schema
is created without dropping existing tables. Replacing populated demo tables
requires the explicit `--replace-demo-data` flag; failures roll back the load.
