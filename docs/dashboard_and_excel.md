# Reporting assets and validation

## Tableau

`python scripts/build_tableau.py` creates `dashboards/Advertising_Current_Demo.twbx`
with current aggregate CSV data, three worksheets and a dashboard. CTR is a
ratio of sums. Counts reconcile to raw controls. No user-level data is embedded.

Automated checks validate the package, XML references, worksheet counts and
aggregate totals. Tableau Desktop/Public is not available in this execution
environment, so native rendering, filters, drill-downs and responsiveness are
**not verified**. Do not claim these capabilities as tested. Open the package in
Tableau Desktop, confirm the CSV connection (repoint to extracted `Data/` if
needed), check all three sheets, and compare totals to `sample_reports/`.
Then add advertiser/campaign/date filters, a campaign hierarchy and a scoped
dashboard action, verify ratios under filtering and measure load time.
This is the remaining manual BI acceptance step, not a completed check.

The old `Ad_Targeting_Revenue_Impact.twbx` remains an explicitly legacy asset.
It refers to the unreproducible version-1 population and must not be presented
as the current model's results. The public Tableau link is also historical.

## Excel

`sample_reports/campaign_investigation.xlsx` is a verified synthetic snapshot.
The Review sheet selects an advertiser and computes SUMIFS/COUNTIFS summaries.
Campaigns contains typed counts, exact VLOOKUPs, CTR formulas, a filterable table,
and separate editable Owner/Status fields. Advertisers is the lookup source.
The workbook was recalculated and rendered with `@oai/artifact-tool`, including
a selected-advertiser change test and formula-error scan. Native Microsoft Excel
was not available. No native PivotTable is claimed.

`scripts/build_excel.mjs` is the authoring source. It requires an environment
with `@oai/artifact-tool` installed; the core Python/Node pipeline does not depend
on that proprietary runtime. Usage:

```
node scripts/build_excel.mjs reports/current/excel_inputs.json /absolute/output/directory
```

Rebuilding a workbook resets investigation fields. Preserve human review notes
in a separate controlled register keyed by advertiser_id + campaign_id, then
merge them explicitly before distribution. Do not overwrite a working analyst
copy to refresh observations.
