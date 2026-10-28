# Review and acceptance

## Automated checks completed

- Seeded generator repeats and all six tables satisfy the current contract.
- Duplicate keys, orphan relationships, missing schema columns and malformed
  timestamps fail. Click attribution rejects events preceding impressions.
- Date-only boundaries include their full UTC day.
- Historical features exclude immature/simultaneous outcomes. Perturbing future
  labels leaves earlier history unchanged. Training-day encodings exclude own-day
  labels, and chronological CV refits encoders with purged boundaries.
- Calibration is fitted before validation, selection uses validation only and
  final test outcomes do not select model or calibration.
- Raw-source controls reconcile to processed and SQL report counts.
- Two PostgreSQL reporting roles see only their own advertiser. Identity access
  and writes are denied. All ten analytical queries execute in PostgreSQL WASM.
- Benchmark queries return identical results before and after indexing.
- Failed refreshes retain last-good reports, and overlapping runs are rejected.
- Excel formulas recalculate under an advertiser change, error scan is empty,
  and all three sheets were visually reviewed.
- All three current notebooks execute as pure Python with saved outputs.

## Remaining native BI acceptance

Open the new packaged workbook in Tableau Desktop/Public. Confirm connection,
marks and ratio calculations, then implement/test advertiser/campaign/date
filters, drill hierarchy and dashboard actions. Measure native load time and
verify entitlement behavior in the actual hosting environment. Structural XML
checks do not establish any of these behaviors. Native Excel testing is also
not available; the artifact-tool recalculation and render checks are recorded.

## Suggested human review

Ask an analytics reviewer to check attribution and report grain, a product
reviewer to approve the success metric, and an engineering reviewer to confirm
identity/availability assumptions. Record real feedback in a PR rather than
claiming collaboration or mentoring based on this checklist alone.
