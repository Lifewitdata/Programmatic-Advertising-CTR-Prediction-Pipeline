# Advertising analytics decision memo

Synthetic demonstration. Observation closes at 2026-01-02T00:00:00 UTC.

## Findings

- 25,000 fully observed impressions reconcile to 493 attributed clicks across source, processed data and SQL aggregates.
- Logistic Regression / platt was selected by validation log loss. Held-out test ROC-AUC is 0.5535; log loss is 0.0871 versus 0.0878 for the constant baseline.
- Top-decile observed lift is 1.84x in the synthetic test set. This is retrospective ranking, not incremental clicks or revenue.

## Actions and trade-offs

1. Use calibrated probability and baseline comparisons before considering a scoring trial. AUC alone cannot establish bid value or financial impact.
2. Review low-volume campaigns with sample sizes and user-cluster intervals before reallocating budget. Segment differences reflect configured simulation effects and confounding.
3. For a real pilot, Product defines success and guardrails; Engineering confirms event/identity contracts and click availability; Delivery owns discrepancy investigation. These are proposed responsibilities, not evidence of collaboration already performed.

## Limits

There are no prices paid, conversions, invoices, randomized treatment assignments or TV airing records here. No ROAS, causal lift, retention or revenue claim is supported. Calendar-time drift, correlated campaigns and attribution delays remain risks. Access controls must be deployed and tested before distributing real client data.
