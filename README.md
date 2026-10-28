# Advertising CTR and reporting analytics

A reproducible portfolio project covering advertising data preparation, SQL,
point-in-time features, probability calibration, aggregate reporting and client
access controls. All observations are synthetic. This is digital advertising
analytics, not a television delivery or billing system.

## Live Tableau dashboard

[View Ad Targeting – Revenue Impact Overview](https://public.tableau.com/app/profile/isfaque.ansari5273/viz/Ad_Targeting_Revenue_Impact/AdTargeting-RevenueImpactOverview)

Published dashboard from the original project. Its alignment with the current
version-2 dataset and model results has not yet been verified. The reproducible
results below describe the current pipeline.

## Current verified demo

The missing original generator has been replaced with a version-2 seeded
generator. These results supersede the old 1M-impression / 84-feature claims.
They are not an exact reconstruction of that unavailable dataset.

| Measure | Current 25,000-impression demo |
|---|---|
| Selected model | Logistic Regression / platt |
| Selection criterion | Validation log loss |
| Final test rows | 4,394 |
| Test ROC-AUC | 0.5535 |
| Test average precision | 0.0229 |
| Test log loss / constant baseline | 0.08709 / 0.08782 |
| Test Brier score | 0.01699 |
| Top-decile observed lift | 1.84x, retrospective synthetic ranking |

Read [model results](sample_reports/model_summary.json),
[reconciliation](sample_reports/reconciliation.csv),
[device uncertainty](sample_reports/device_intervals.csv) and the
[decision memo](sample_reports/decision_memo.md). No financial or causal uplift
is claimed. A small AUC improvement or lift estimate is not evidence of a
successful real-world intervention.

## Run from a fresh clone

Use Python 3.12 and Node 22+ on Linux/macOS or WSL. The report runner uses POSIX
file locks and atomic symlinks. Python dependencies and the PostgreSQL WASM
package are version-pinned.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
bash scripts/refresh_reports.sh 25000
python scripts/execute_notebooks.py
```

The shell command generates six raw tables, validates them, fits/evaluates models,
reconciles reports, verifies SQL and access policies, packages Tableau data and
runs tests. Notebook execution supports the pure-Python cells used here without
requiring networked Jupyter kernels. Open the resulting `.ipynb` files normally
in Jupyter/VS Code if preferred. To scale the full pipeline, change the shell
argument (for example `1000000`); the shipped sample results remain a 25K run.

Reports are written to a new run directory and promoted to `reports/current`
only after core Python checks succeed. Subsequent PostgreSQL, package and test
checks fail the shell command if unsuccessful. A failed core refresh preserves
the last good report. These are deterministic full rebuilds, not an incremental
streaming system. Raw identity rows and model bundles remain local and ignored.

## Data and modeling

Six tables represent users, advertisers, campaigns, creatives, impressions and
clicks. Generated clicks arrive 1 second to 24 hours after an impression.
The observation manifest declares the final observation cutoff. Only complete
24-hour attribution windows enter the labeled population.

The current model uses 17 features. Historical counts and CTR include only
matured outcomes strictly before scoring. Day-block training target encodings
exclude their own day's outcomes. Encoders and models are refitted per forward
CV fold. Fit, calibration-fit, validation and test boundaries are chronological,
shared through configuration and purged for outcome availability. Platt scaling
is fitted on calibration data; validation chooses the raw/calibrated candidate;
then the selected model is evaluated once on test. See the executed
[feature notebook](notebooks/feature_engineering.ipynb) and
[model notebook](notebooks/modeling.ipynb).

The selected model's own explanation is exported. Logistic regression uses
standardized coefficients; CatBoost, if selected on a different run, uses native
CatBoost SHAP contributions. These explain the raw model, not its Platt mapping.

## SQL, reconciliation and access

- PostgreSQL schema with primary keys, foreign keys, unique/check constraints
  and workload-related indexes.
- Ten analytical queries demonstrate joins, CTEs, rankings, grouping sets and
  impression-weighted seven-calendar-day CTR.
- Aggregate reports run through SQL and reconcile to independently attributed
  raw source totals. Rates are ratios of sums.
- PostgreSQL row-level policies isolate advertiser aggregates; negative tests
  deny raw identity access and writes for the reporting roles.
- An isolated benchmark checks identical results before/after a composite index,
  records EXPLAIN ANALYZE/BUFFERS JSON and seven warmed executions per condition.
  This run measured 2.708 ms before versus
  0.094 ms after in **PGlite PostgreSQL WASM**.
  These are local demonstration measurements, not production server SLAs.

To use a separate local PostgreSQL server, set `CTR_DB_HOST`, `CTR_DB_PORT`,
`CTR_DB_NAME`, `CTR_DB_USER` and `CTR_DB_PASSWORD`, then run
`python -m src.database.load_to_postgres`. Populated demo tables require the
explicit `--replace-demo-data` flag for a transactional replacement. The core
fresh-clone demo and SQL verification do not require a server or credentials.

## Dashboards and Excel

- [Current Tableau package](dashboards/Advertising_Current_Demo.twbx): aggregate
  campaign data, three worksheets, a dashboard and a ratio-of-sums CTR field.
  Package/XML/totals checks pass; native Tableau rendering and interactions
  require the remaining Desktop/Public acceptance check described
  [here](docs/dashboard_and_excel.md). They are not claimed as verified.
- [Excel investigation report](sample_reports/campaign_investigation.xlsx):
  selectable advertiser summary, SUMIFS/COUNTIFS, exact VLOOKUP, CTR formulas,
  a filterable campaign table and editable review fields. Recalculation,
  formula-error checks and rendered layouts were verified with artifact-tool.
  Native Microsoft Excel and native PivotTables were not tested/claimed.
  The included authoring script requires `@oai/artifact-tool`; it is optional
  and is not a dependency of the open Python pipeline.
- The old Tableau revenue workbook, public Tableau link and old figure assets
  are historical version-1 outputs. Do not combine them with current metrics.
- `ancillary/` remains a separate, optional travel purchase example and is not
  part of the advertising refresh, validation or current results.

## Documentation and review

[KPI dictionary](docs/kpi_dictionary.md),
[governance and lineage](docs/governance_and_lineage.md),
[feature contract](notebooks/FEATURE_MANIFEST.md),
[evaluation method](notebooks/MODELING_README.md).

CI runs the reproducible demo, tests and PostgreSQL verification on pull requests.
The workflow can also be run manually. It does not send emails or post reports.
Collaboration/mentoring cannot be established by a portfolio repository alone;
the proposed review roles and acceptance checklist are explicitly documented.

## Limits

Synthetic populations do not establish real advertiser behavior or customer
impact. Device intervals use user-cluster resampling but do not account for every
possible source of dependence or generator uncertainty. There are no conversions,
prices paid, invoices, actual television airings or randomized treatments, so
ROAS, TV delivery, causal impact, retention and realized revenue are out of scope.
No live scoring API or latency claim is made. Database RLS does not protect an
offline workbook after export; real client packages require scoped distribution.
