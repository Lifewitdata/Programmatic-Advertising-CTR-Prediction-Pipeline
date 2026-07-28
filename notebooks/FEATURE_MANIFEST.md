# Feature Manifest — Phase 7

**84 total modeling features**: 17 base attributes carried through ETL + 67
newly engineered in `notebooks/02_feature_engineering.ipynb`.

Two leakage-safe encoding techniques are used throughout — see the notebook
for the full explanation and a hand-verified toy-example sanity check:

- **Expanding-window-excluding-current**: for time-ordered entities
  (campaign, user, creative, publisher, etc.) — a feature for a given row
  uses only that entity's history strictly before this impression.
- **Fit-on-train / transform-on-all**: for static categoricals and
  interactions — encoding computed from training rows only, applied to
  validation/test, with a global-CTR fallback for unseen categories.

A correlation-based leakage check confirmed the max absolute correlation
between any feature and the label is 0.036 — real but modest signal, no
red flags.

## Time features (8)
| Feature | Why it helps |
|---|---|
| `hour_sin`, `hour_cos` | Cyclical encoding of hour-of-day; preserves that hour 23 and 0 are adjacent in real time |
| `dow_sin`, `dow_cos` | Cyclical encoding of day-of-week |
| `is_business_hours`, `is_late_night` | Coarser time-of-day buckets, cheap and stable even where raw hour is noisy |
| `days_since_campaign_start`, `days_until_campaign_end`, `campaign_flight_progress` | Captures within-campaign performance drift (ramp-up/pacing-down effects) independent of the impression's own attributes |

## Historical CTR features — expanding window (27)
For each of `campaign`, `creative`, `publisher`, `device`, `country`,
`browser`, `ad_position`, `category`, `hour_bucket`: `*_historical_ctr`,
`*_historical_impressions`, `*_historical_clicks`.

**Why:** the single strongest class of CTR features in real ad systems —
"how has this entity performed so far" is a direct, Bayesian-smoothed proxy
for its future performance, and EDA (Phase 6) confirmed real, persistent
differences across every one of these entities.

## User activity and recency (7)
| Feature | Why it helps |
|---|---|
| `user_historical_ctr`, `user_lifetime_impressions`, `user_lifetime_clicks` | Per-user propensity, smoothed for cold-start users |
| `user_distinct_campaigns_seen`, `user_distinct_advertisers_seen` | Ad-diversity exposure — users seeing many different advertisers may behave differently than those in a narrow retargeting loop |
| `seconds_since_user_last_impression` | Recency of last exposure — ties into the fatigue pattern found in EDA |
| `user_account_age_days` | Newer accounts may behave differently than established ones |
| `user_interest_matches_category` | Legitimate serving-time signal: does the user's stated interest match the campaign being shown |

## Campaign daily rolling stats (3)
`campaign_impressions_prev_day`, `campaign_clicks_prev_day`,
`campaign_ctr_prev_day` — "is this campaign hot or cold right now,"
computed from the previous calendar day only (no same-day lookahead).

## Frequency encoding (5)
`user_id_frequency`, `campaign_id_frequency`, `creative_id_frequency`,
`publisher_domain_frequency`, `advertiser_id_frequency` — fit on train
only. High-frequency entities have more reliable historical stats;
frequency itself is a useful confidence signal for the model to weigh
alongside the historical CTR features.

## Target encoding, static categoricals (5)
`age_group`, `gender`, `objective`, `target_device`, `creative_type` —
mean click rate per category, train-fit, Bayesian-smoothed.

## Interaction features (5)
`device_x_creative_type_ctr`, `ad_position_x_creative_type_ctr`,
`hour_bucket_x_is_weekend_ctr`, `device_x_ad_position_ctr`,
`category_x_device_ctr` — pairwise combinations flagged by EDA as plausibly
jointly informative beyond their individual main effects (e.g. video ads
may perform disproportionately well specifically on mobile).

## Deliberately excluded
`click_propensity` (the latent, ground-truth click-generating variable from
Phase 3) is never used as a feature — a real production system has no
access to a user's "true" propensity to click, only to observable behavior.
Including it would be direct label leakage, not a legitimate feature.
