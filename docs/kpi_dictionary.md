# Metric definitions

All current results are synthetic, generator version 2. Timestamps are UTC.
The observation cutoff is in `data/raw/manifest.json`. Report freshness is the
latest source impression timestamp, not the time the notebook was opened.

| Metric | Grain and definition | Exclusions and interpretation |
|---|---|---|
| Eligible impressions | One row per impression ID whose complete 24h click window is observed | Excludes incomplete windows; duplicate IDs are rejected |
| Attributed clicks | At most one click per impression, timestamp between impression and +24h inclusive | Later clicks are not attributed; pre-impression clicks are rejected |
| CTR | SUM(attributed clicks) / SUM(eligible impressions) at the chosen date/advertiser/campaign/device/country grain | Undefined for zero impressions. Never average row-level CTRs |
| 7-day CTR | Clicks / impressions for the current and preceding six calendar dates | Weighted by impressions, not seven arbitrary rows |
| Test ROC-AUC | Ranking metric on the held-out chronological test period | Does not establish probability calibration or financial value |
| Average precision | Average precision score on test outcomes; baseline is prevalence | This implementation reports AP, not trapezoidal PR area |
| Log loss | Mean binary negative log likelihood | Selection uses validation log loss only; lower is better |
| Brier score | Mean squared difference between probability and outcome | Calibration diagnostic, lower is better |
| Decile lift | Observed CTR in a ranked test decile / overall test CTR | Retrospective synthetic ranking, not incremental effect |
| Reconciliation difference | SQL report total minus independently attributed raw-source control | Must equal zero for impressions and clicks |

## Contract and ownership

Analyst owns definitions and code. Proposed Product reviewer confirms objective
and attribution policy. Engineering validates event identity and timestamp
availability. Delivery investigates exceptions. These are planned review roles,
not claims that an actual cross-functional review or mentoring occurred.

Reports perform deterministic full rebuilds. Late events require a rebuild from
the updated source, preserving a declared observation cutoff. The current seeded
demo does not simulate a live incremental source or schema migration service.
The canonical Python refresh emits aggregate CSVs; Excel and Tableau packages
are separately authored views whose refresh steps are documented.
