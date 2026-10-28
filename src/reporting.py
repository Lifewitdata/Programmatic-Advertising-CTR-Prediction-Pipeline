"""Auditable aggregate reporting; no identity or user-profile fields are exported."""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DAILY_SQL = '''
SELECT date(timestamp) AS event_date, advertiser_id, campaign_id, device, country,
       COUNT(*) AS impressions, SUM(clicked) AS clicks
FROM eligible_impressions
GROUP BY date(timestamp), advertiser_id, campaign_id, device, country
ORDER BY event_date, advertiser_id, campaign_id, device, country
'''


def cluster_intervals(frame, seed=42, repetitions=400):
    """User-cluster bootstrap handles repeated impressions per user.

    Exploratory descriptive uncertainty conditional on the synthetic population.
    No claim of causal device effects or population representativeness.
    """
    counts = frame.groupby(['user_id', 'device']).clicked.agg(['sum', 'count']).unstack(fill_value=0)
    devices = sorted(frame.device.unique())
    ys = counts['sum'].reindex(columns=devices, fill_value=0).to_numpy()
    ns = counts['count'].reindex(columns=devices, fill_value=0).to_numpy()
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(repetitions):
        ix = rng.integers(0, len(counts), len(counts))
        denominator = ns[ix].sum(axis=0)
        samples.append(np.divide(ys[ix].sum(axis=0), denominator,
            out=np.full(len(devices), np.nan), where=denominator > 0))
    samples = np.asarray(samples)
    rows = []
    for i, device in enumerate(devices):
        low, high = np.nanquantile(samples[:, i], [0.025, 0.975])
        rows.append({'device': device, 'impressions': int(ns[:, i].sum()),
            'clicks': int(ys[:, i].sum()), 'ctr': ys[:, i].sum() / ns[:, i].sum(),
            'ci_low': low, 'ci_high': high, 'method': '400 user-cluster bootstrap resamples, 95% percentile CI'})
    contrast = {}
    if 'mobile' in devices and 'desktop' in devices:
        difference = samples[:, devices.index('mobile')] - samples[:, devices.index('desktop')]
        low, high = np.nanquantile(difference, [0.025, 0.975])
        contrast = {'comparison': 'mobile minus desktop CTR', 'ci_low': float(low), 'ci_high': float(high),
                    'zero_excluded': bool(low > 0 or high < 0),
                    'interpretation': 'Exploratory association in generated data; no causal or real-market conclusion'}
    return pd.DataFrame(rows), contrast


def export_reports(frame, tables, model_summary, manifest, output='reports/current'):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(':memory:')
    frame[['timestamp', 'advertiser_id', 'campaign_id', 'device', 'country', 'clicked']].to_sql('eligible_impressions', conn, index=False)
    daily = pd.read_sql_query(DAILY_SQL, conn)
    conn.close()
    # Independent source controls: use raw events and eligibility IDs, not frame.clicked.
    raw = tables['impressions'][['impression_id', 'timestamp']].copy()
    raw.timestamp = pd.to_datetime(raw.timestamp)
    eligible = raw[raw.timestamp + pd.Timedelta(hours=24) <= pd.Timestamp(manifest['observed_through'])]
    clicked = tables['clicks'].merge(eligible, on='impression_id', validate='one_to_one')
    clicked.click_timestamp = pd.to_datetime(clicked.click_timestamp)
    source_clicks = ((clicked.click_timestamp >= clicked.timestamp) &
                     (clicked.click_timestamp <= clicked.timestamp + pd.Timedelta(hours=24))).sum()
    records = []
    for metric, expected, processed, reported in [
        ('impressions', len(eligible), len(frame), daily.impressions.sum()),
        ('attributed_clicks', source_clicks, frame.clicked.sum(), daily.clicks.sum())]:
        records.append({'metric': metric, 'source_total': int(expected), 'processed_total': int(processed),
            'report_total': int(reported), 'difference': int(reported - expected),
            'status': 'MATCH' if expected == processed == reported else 'MISMATCH'})
    reconciliation = pd.DataFrame(records)
    reconciliation.to_csv(out / 'reconciliation.csv', index=False)
    if reconciliation.status.ne('MATCH').any():
        raise ValueError('Source-to-report reconciliation failed')
    daily['ctr'] = daily.clicks / daily.impressions
    daily['scope'] = 'synthetic fully observed impressions, 24h attribution, UTC'
    daily.to_csv(out / 'campaign_daily.csv', index=False)
    # Publish totals and ratios at campaign level, never average row CTRs.
    campaign = daily.groupby(['advertiser_id', 'campaign_id'], as_index=False)[['impressions', 'clicks']].sum()
    campaign['ctr'] = campaign.clicks / campaign.impressions
    campaign['review_reason'] = np.where(campaign.clicks.eq(0), 'No observed clicks; investigate sample size', 'Review with confidence interval and campaign objective')
    campaign.to_csv(out / 'campaign_review.csv', index=False)
    intervals, contrast = cluster_intervals(frame)
    intervals.to_csv(out / 'device_intervals.csv', index=False)
    (out / 'device_contrast.json').write_text(json.dumps(contrast, indent=2) + '\n')
    # Lookup values and raw grouped counts for the optional Excel builder.
    excel = {'campaigns': campaign.to_dict('records'),
             'advertisers': tables['advertisers'][['advertiser_id', 'advertiser_name']].to_dict('records'),
             'reconciliation': records, 'manifest': manifest}
    (out / 'excel_inputs.json').write_text(json.dumps(excel, indent=2) + '\n')
    run = {'synthetic': True, 'observed_through': manifest['observed_through'],
           'source_max_impression_time': str(frame.timestamp.max()),
           'raw_rows': manifest['rows'], 'eligible_rows': len(frame),
           'reported_impressions': int(daily.impressions.sum()),
           'reported_clicks': int(daily.clicks.sum()), 'reconciliation': 'MATCH',
           'refresh_mode': 'deterministic full rebuild; atomic promotion by run_pipeline',
           'lineage': ['data/raw/*.csv', 'eligible labels', 'point-in-time features',
                       'SQLite DAILY_SQL', 'reports/current/campaign_daily.csv', 'Tableau/Excel']}
    (out / 'run_manifest.json').write_text(json.dumps(run, indent=2) + '\n')
    memo = f'''# Advertising analytics decision memo

Synthetic demonstration. Observation closes at {manifest['observed_through']} UTC.

## Findings

- {len(frame):,} fully observed impressions reconcile to {int(daily.clicks.sum()):,} attributed clicks across source, processed data and SQL aggregates.
- {model_summary['selected_model']} was selected by validation log loss. Held-out test ROC-AUC is {model_summary['test']['roc_auc']:.4f}; log loss is {model_summary['test']['log_loss']:.4f} versus {model_summary['test_baseline']['log_loss']:.4f} for the constant baseline.
- Top-decile observed lift is {model_summary['top_decile_lift']:.2f}x in the synthetic test set. This is retrospective ranking, not incremental clicks or revenue.

## Actions and trade-offs

1. Use calibrated probability and baseline comparisons before considering a scoring trial. AUC alone cannot establish bid value or financial impact.
2. Review low-volume campaigns with sample sizes and user-cluster intervals before reallocating budget. Segment differences reflect configured simulation effects and confounding.
3. For a real pilot, Product defines success and guardrails; Engineering confirms event/identity contracts and click availability; Delivery owns discrepancy investigation. These are proposed responsibilities, not evidence of collaboration already performed.

## Limits

There are no prices paid, conversions, invoices, randomized treatment assignments or TV airing records here. No ROAS, causal lift, retention or revenue claim is supported. Calendar-time drift, correlated campaigns and attribution delays remain risks. Access controls must be deployed and tested before distributing real client data.
'''
    (out / 'decision_memo.md').write_text(memo)
    return run
