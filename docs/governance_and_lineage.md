# Data access, lineage and distribution

## Lineage

`src/generate_data.py` + versioned YAML configuration produce six raw CSVs and
an observation manifest. SHA-256 controls identify the inputs for each run.
`validate.py` checks schema, keys, links and timestamps. `features.labels`
defines eligible outcomes, and `build_features` calculates only matured history.
`TemporalEncoder` fits chronological training encodings. `modeling.train`
fits the model, calibration and validation selection before final test scoring.
`reporting.DAILY_SQL` creates aggregate data, checked against raw source totals.
Tableau and Excel use these aggregate extracts, never private score tables.

## Access implementation

`sql/reporting_security.sql` creates a separate reporting schema and two NOLOGIN
demo roles. Each can SELECT only its advertiser's aggregate rows. The roles
cannot SELECT user identities or write the reporting table. `verify_postgres.mjs`
executes both positive and negative assertions in PostgreSQL WASM.

NOLOGIN roles demonstrate policy behavior; they do not provision real employee
accounts. Table owners and superusers are trusted administrators and can bypass
ordinary tenant separation. Real deployment needs separate least-privilege
logins, TLS, identity-provider mapping, secret management and platform-specific
Tableau entitlement enforcement. A visual dashboard filter is not security.

## Distribution rules

Only synthetic aggregates and reviewed sample outputs are committed. Raw user
rows, latent propensity fields, row-level predictions, model bundles, credentials
and operational logs are ignored by Git. An Excel or packaged Tableau extract is
an offline copy: database RLS cannot protect it after download. Real client exports
must be scoped by the authenticated role before packaging, reviewed and shared
through restricted channels. Avoid publicly publishing small sensitive groups.

The demo deliberately does not infer client identities, revenue or sensitive
attributes from external sources. It contains no real personal information.

## Failure and refresh behavior

Source errors fail explicitly; PostgreSQL failures do not silently select stale
CSV files. A lock prevents overlapping refreshes. Successful reports are promoted
using an atomic symlink swap; failed runs retain the last good report. This runner
targets Linux/macOS or WSL. On interruption, the OS releases the advisory lock.
Generated data/processed artifacts are local work products, not versioned serving
state. Consumers should use a completed report snapshot rather than reading
processed intermediates while a refresh is running.
