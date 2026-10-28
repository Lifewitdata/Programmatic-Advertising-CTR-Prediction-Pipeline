import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features import labels, build_features, TemporalEncoder, split_for_model
from src.generate_data import generate
from src.etl.transform import time_based_split
from src.etl.validate import validate, ValidationError
from src.reporting import export_reports


@pytest.fixture
def config():
    return yaml.safe_load(Path('config/etl_config.yaml').read_text())


@pytest.fixture
def tables():
    cfg = yaml.safe_load(Path('config/data_gen_config.yaml').read_text())
    return generate(cfg, 12000)


def test_seeded_generator_repeats_and_respects_schema(tables):
    cfg = yaml.safe_load(Path('config/data_gen_config.yaml').read_text())
    second = generate(cfg, 12000)
    for name in tables:
        pd.testing.assert_frame_equal(tables[name], second[name])
    assert (tables['clicks'].merge(tables['impressions'], on='impression_id').click_timestamp >=
            tables['clicks'].merge(tables['impressions'], on='impression_id').timestamp).all()


def test_date_only_boundary_includes_full_day():
    frame = pd.DataFrame({'timestamp': pd.to_datetime([
        '2025-11-30 00:00:00', '2025-11-30 23:59:59', '2025-12-01 00:00:00',
        '2025-12-15 23:59:59', '2025-12-16 00:00:00'])})
    tr, va, te = time_based_split(frame.assign(clicked=0), '2025-11-30', '2025-12-15')
    assert [len(tr), len(va), len(te)] == [2, 2, 1]


def test_invalid_date_order_rejected():
    with pytest.raises(ValueError):
        time_based_split(pd.DataFrame(), '2025-12-15', '2025-11-30')


def test_labels_require_mature_window_and_attribution_limit():
    imp = pd.DataFrame({'impression_id': [1, 2, 3], 'timestamp': pd.to_datetime([
        '2025-01-01', '2025-01-01', '2025-01-02 12:00'], format='mixed')})
    clk = pd.DataFrame({'impression_id': [1, 2], 'click_timestamp': pd.to_datetime([
        '2025-01-02', '2025-01-02 00:00:01'], format='mixed')})
    result = labels(imp, clk, '2025-01-03')
    assert result.impression_id.tolist() == [1, 2]
    assert result.clicked.tolist() == [1, 0]


def test_duplicate_label_join_rejected():
    imp = pd.DataFrame({'impression_id': [1], 'timestamp': pd.to_datetime(['2025-01-01'])})
    clk = pd.DataFrame({'impression_id': [1, 1], 'click_timestamp': pd.to_datetime(['2025-01-01'] * 2)})
    with pytest.raises(ValueError, match='one-to-one'):
        labels(imp, clk, '2025-01-03')


def test_click_before_impression_rejected():
    with pytest.raises(ValueError, match='precede'):
        labels(pd.DataFrame({'impression_id': [1], 'timestamp': pd.to_datetime(['2025-01-02'])}),
               pd.DataFrame({'impression_id': [1], 'click_timestamp': pd.to_datetime(['2025-01-01'])}), '2025-01-04')


def test_history_excludes_unavailable_and_simultaneous_outcomes():
    from src.features import add_history
    frame = pd.DataFrame({'user_id': [1] * 4,
        'timestamp': pd.to_datetime(['2025-01-01', '2025-01-01 12:00', '2025-01-02', '2025-01-02 00:00:01'], format='mixed'),
        'label_available_at': pd.to_datetime(['2025-01-02', '2025-01-02 12:00', '2025-01-03', '2025-01-03 00:00:01'], format='mixed'),
        'clicked': [1, 0, 1, 0]})
    result = add_history(frame, 'user_id', 'user')
    assert result.user_history_clicks.tolist() == [0, 0, 0, 1]
    assert result.user_history_impressions.tolist() == [0, 0, 0, 1]


def test_future_labels_cannot_change_earlier_features(tables):
    frame = labels(tables['impressions'], tables['clicks'], '2026-01-02')
    original = build_features(frame)
    changed = frame.copy()
    cutoff = pd.Timestamp('2025-11-01')
    changed.loc[changed.timestamp >= cutoff, 'clicked'] = 1 - changed.loc[changed.timestamp >= cutoff, 'clicked']
    updated = build_features(changed)
    cols = [c for c in original if '_history_' in c]
    pd.testing.assert_frame_equal(original.loc[original.timestamp < cutoff, cols], updated.loc[updated.timestamp < cutoff, cols])


def test_encoder_day_does_not_encode_own_labels(tables):
    frame = build_features(labels(tables['impressions'], tables['clicks'], '2026-01-02'))
    same_day = frame[frame.timestamp.dt.floor('D').eq(pd.Timestamp('2025-10-01'))].reset_index(drop=True)
    a = TemporalEncoder().fit_transform(same_day)
    same_day['clicked'] = 1 - same_day.clicked
    b = TemporalEncoder().fit_transform(same_day)
    pd.testing.assert_frame_equal(a, b)


def test_encoder_rejects_unavailable_training_outcomes(tables):
    frame = build_features(labels(tables['impressions'], tables['clicks'], '2026-01-02'))
    encoder = TemporalEncoder()
    encoder.fit_transform(frame.iloc[:500])
    with pytest.raises(ValueError, match='not yet available'):
        encoder.transform(frame.iloc[:10])


def test_split_purges_outcomes_crossing_boundaries(tables, config):
    frame = build_features(labels(tables['impressions'], tables['clicks'], '2026-01-02'))
    parts = split_for_model(frame, config)
    for left, right in [('fit', 'calibration'), ('calibration', 'validation'), ('validation', 'test')]:
        assert parts[left].label_available_at.max() < parts[right].timestamp.min()
    ids = [set(part.impression_id) for part in parts.values()]
    assert sum(map(len, ids)) == len(set.union(*ids))


@pytest.mark.parametrize('change', ['orphan', 'duplicate_click', 'bad_timestamp', 'bad_creative_campaign', 'missing_column'])
def test_validation_rejects_broken_contracts(tables, config, change):
    data = {k: v.copy() for k, v in tables.items()}
    if change == 'orphan':
        data['impressions'].loc[0, 'creative_id'] = -999
    elif change == 'duplicate_click':
        data['clicks'].loc[1, 'impression_id'] = data['clicks'].loc[0, 'impression_id']
    elif change == 'bad_timestamp':
        data['impressions']['timestamp'] = data['impressions'].timestamp.astype(str)
        data['impressions'].loc[0, 'timestamp'] = 'not-a-date'
    elif change == 'bad_creative_campaign':
        data['impressions'].loc[0, 'campaign_id'] = data['campaigns'].campaign_id.max()
    else:
        data['impressions'] = data['impressions'].drop(columns='device')
    with pytest.raises(ValidationError):
        validate(data, config)


def test_reconciliation_catches_dropped_impression(tables, tmp_path):
    frame = labels(tables['impressions'], tables['clicks'], '2026-01-02').iloc[1:]
    with pytest.raises(ValueError, match='reconciliation'):
        export_reports(frame, tables, {}, {'observed_through': '2026-01-02'}, tmp_path)


def test_model_summary_and_public_exports_are_current_and_aggregate():
    path = Path('reports/current/model_summary.json')
    if not path.exists():
        pytest.skip('Run demo for report integration assertions')
    summary = json.loads(path.read_text())
    assert summary['generator_version'] == 2 and summary['synthetic']
    daily = pd.read_csv('reports/current/campaign_daily.csv')
    assert 'user_id' not in daily and 'click_propensity' not in daily
    assert not daily.duplicated(['event_date', 'advertiser_id', 'campaign_id', 'device', 'country']).any()
    recon = pd.read_csv('reports/current/reconciliation.csv')
    assert recon.status.eq('MATCH').all()
