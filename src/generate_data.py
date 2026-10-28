"""Seeded synthetic advertising data; this replaces the unavailable legacy generator.

Every event uses naive UTC. Clicks arrive 1 second to 24 hours after an
impression; observation continues for 24 hours beyond the last impression.
The synthetic population and all results differ from the legacy dataset.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def generate(config, n_impressions=None):
    rng = np.random.default_rng(config['random_seed'])
    v, ref, model = config['volumes'], config['reference_data'], config['click_model']
    n = n_impressions if n_impressions is not None else v['n_impressions']
    if n < 1000:
        raise ValueError('Use at least 1000 impressions for a meaningful demo')
    # Scale dimensions down for a small, quick demo.
    nu, na = min(v['n_users'], max(100, n // 10)), min(v['n_advertisers'], max(5, n // 1000))

    def choice(items, key, size):
        weights = np.array([x['weight'] for x in items], dtype=float)
        return rng.choice([x[key] for x in items], size=size, p=weights / weights.sum())

    users = pd.DataFrame({
        'user_id': np.arange(1, nu + 1),
        'country': choice(ref['countries'], 'code', nu),
        'primary_device': choice(ref['devices'], 'type', nu),
        'age_group': rng.choice(['18-24', '25-34', '35-44', '45+'], nu),
        'gender': rng.choice(['unknown', 'female', 'male'], nu),
        'primary_interest': rng.choice(ref['interest_categories'], nu),
        'n_interests': rng.integers(1, 6, nu),
        'account_created_date': '2025-01-01',
        # Simulation parameter only. Never enter this field into features/reports.
        'click_propensity': np.clip(rng.normal(0.5, 0.15, nu), 0.01, 0.99).round(4),
    })
    advertisers = pd.DataFrame({
        'advertiser_id': np.arange(1, na + 1),
        'advertiser_name': [f'Synthetic advertiser {i}' for i in range(1, na + 1)],
        'industry': rng.choice(ref['advertiser_industries'], na),
        'hq_country': choice(ref['countries'], 'code', na),
    })
    aid = np.repeat(advertisers.advertiser_id, rng.integers(
        v['campaigns_per_advertiser_min'], v['campaigns_per_advertiser_max'] + 1, na))
    nc = len(aid)
    campaigns = pd.DataFrame({
        'campaign_id': np.arange(1, nc + 1), 'advertiser_id': aid,
        'category': rng.choice(ref['campaign_categories'], nc),
        'objective': choice(ref['campaign_objectives'], 'name', nc),
        'target_country': choice(ref['countries'], 'code', nc),
        'target_device': choice(ref['devices'], 'type', nc),
        'start_date': config['date_range']['start_date'],
        'end_date': config['date_range']['end_date'],
        'daily_budget_usd': rng.integers(100, 1000, nc),
        'bid_strategy': 'synthetic_cpm',
    })
    days = (pd.Timestamp(config['date_range']['end_date']) - pd.Timestamp(config['date_range']['start_date'])).days + 1
    campaigns['total_budget_usd'] = campaigns.daily_budget_usd * days
    cid = np.repeat(campaigns.campaign_id, rng.integers(
        v['creatives_per_campaign_min'], v['creatives_per_campaign_max'] + 1, nc))
    creatives = pd.DataFrame({
        'creative_id': np.arange(1, len(cid) + 1), 'campaign_id': cid,
        'creative_type': choice(ref['creative_types'], 'type', len(cid)),
        'size': '300x250', 'headline': 'Synthetic demonstration creative',
    })
    start = pd.Timestamp(config['date_range']['start_date'])
    seconds = rng.integers(0, days * 86400, n)
    impressions = pd.DataFrame({
        'impression_id': np.arange(1, n + 1),
        'timestamp': start + pd.to_timedelta(seconds, unit='s'),
        'user_id': rng.integers(1, nu + 1, n),
        'creative_id': rng.integers(1, len(cid) + 1, n),
        'ad_position': choice(ref['ad_positions'], 'position', n),
        'browser': choice(ref['browsers'], 'name', n),
        'publisher_domain': rng.choice(ref['publisher_domains'], n),
        'floor_price_usd': rng.uniform(0.1, 4, n).round(3),
    }).merge(users[['user_id', 'country', 'primary_device']], on='user_id', validate='many_to_one')
    impressions = impressions.merge(creatives[['creative_id', 'campaign_id', 'creative_type']], on='creative_id', validate='many_to_one')
    impressions = impressions.merge(campaigns[['campaign_id', 'advertiser_id', 'category', 'objective', 'target_device']], on='campaign_id', validate='many_to_one')
    impressions['device'] = impressions.primary_device
    impressions['os'] = 'unknown'
    for device, oses in ref['operating_systems'].items():
        mask = impressions.device.eq(device)
        impressions.loc[mask, 'os'] = choice(oses, 'name', mask.sum())
    impressions = impressions.sort_values(['timestamp', 'impression_id']).reset_index(drop=True)
    impressions['hour_of_day'] = impressions.timestamp.dt.hour
    impressions['day_of_week'] = impressions.timestamp.dt.dayofweek
    impressions['is_weekend'] = impressions.day_of_week.ge(5)
    impressions['date'] = impressions.timestamp.dt.strftime('%Y-%m-%d')
    impressions['hour_bucket'] = pd.cut(impressions.hour_of_day,
        [-1, 5, 11, 17, 22, 23], labels=['late_night', 'morning', 'afternoon', 'evening', 'night']).astype(str)
    impressions['prior_impressions_today'] = impressions.groupby(['user_id', 'date']).cumcount()
    latent = rng.normal(0, model['user_propensity_std'], nu)
    base = model['base_ctr']
    logit = np.full(n, np.log(base / (1 - base))) + latent[impressions.user_id.to_numpy() - 1]
    for col, effects in [('device', 'device_effect'), ('creative_type', 'creative_type_effect'),
                         ('ad_position', 'ad_position_effect'), ('hour_bucket', 'hour_effect'),
                         ('objective', 'objective_effect')]:
        logit += impressions[col].map(model[effects]).to_numpy()
    interests = impressions.user_id.map(users.set_index('user_id').primary_interest)
    logit += interests.eq(impressions.category) * model['interest_match_effect']
    logit += impressions.is_weekend * model['weekend_effect']
    logit -= impressions.prior_impressions_today.clip(upper=model['fatigue_cap']) * model['fatigue_decay_per_prior_impression']
    clicked = rng.random(n) < 1 / (1 + np.exp(-logit))
    clicks = impressions.loc[clicked, ['impression_id', 'timestamp']].copy()
    clicks['click_timestamp'] = clicks.pop('timestamp') + pd.to_timedelta(rng.integers(1, 86401, len(clicks)), unit='s')
    clicks = clicks.reset_index(drop=True)
    clicks.insert(0, 'click_id', np.arange(1, len(clicks) + 1))
    tables = dict(users=users, advertisers=advertisers, campaigns=campaigns,
                  creatives=creatives, impressions=impressions, clicks=clicks)
    return tables


def main(config_path='config/data_gen_config.yaml', n_impressions=None):
    config = yaml.safe_load(Path(config_path).read_text())
    tables = generate(config, n_impressions)
    out = Path(config['output_dir'])
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(out / f'{name}.csv', index=False, lineterminator='\n')
    observed_through = pd.Timestamp(config['date_range']['end_date']) + pd.Timedelta(days=2)
    manifest = {'generator_version': 2, 'seed': config['random_seed'], 'synthetic': True,
                'observed_through': observed_through.isoformat(),
                'attribution_hours': 24, 'rows': {k: len(v) for k, v in tables.items()}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return tables, manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/data_gen_config.yaml')
    parser.add_argument('--n-impressions', type=int)
    args = parser.parse_args()
    main(args.config, args.n_impressions)
