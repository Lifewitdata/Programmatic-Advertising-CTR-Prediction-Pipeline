"""Point-in-time features and chronological out-of-fold target encoding.

An impression contributes a matured outcome only after its complete 24-hour
attribution window has closed. Strict as-of joins exclude simultaneous outcomes.
No label from a calibration, validation, or test row enters a fitted encoder.
"""
import numpy as np
import pandas as pd

PRIOR = 0.02  # Declared simulation prior; never estimated from future labels.
CATEGORICAL = ['device', 'creative_type', 'ad_position', 'country', 'objective', 'hour_bucket']
NUMERIC = ['hour_of_day', 'day_of_week', 'is_weekend', 'prior_impressions_today',
           'floor_price_usd', 'campaign_history_impressions', 'campaign_history_clicks',
           'campaign_history_ctr', 'user_history_impressions', 'user_history_clicks',
           'user_history_ctr']


def labels(impressions, clicks, observed_through, hours=24):
    if impressions.impression_id.duplicated().any() or clicks.impression_id.duplicated().any():
        raise ValueError('Label join must be one-to-one')
    frame = impressions.copy()
    frame['timestamp'] = pd.to_datetime(frame.timestamp)
    events = clicks[['impression_id', 'click_timestamp']].copy()
    events['click_timestamp'] = pd.to_datetime(events.click_timestamp)
    frame = frame.merge(events, on='impression_id', how='left', validate='one_to_one')
    window_end = frame.timestamp + pd.Timedelta(hours=hours)
    present = frame.click_timestamp.notna()
    if (present & (frame.click_timestamp < frame.timestamp)).any():
        raise ValueError('A click cannot precede its impression')
    frame['clicked'] = (present & (frame.click_timestamp <= window_end)).astype(int)
    frame['label_available_at'] = window_end
    # Include only observations with fully observed attribution windows.
    return frame.loc[window_end <= pd.Timestamp(observed_through)].drop(columns='click_timestamp').reset_index(drop=True)


def add_history(frame, entity, prefix):
    """24-hour-matured outcomes available strictly before each scoring timestamp."""
    result = frame.copy()
    history = frame.groupby([entity, 'label_available_at'], as_index=False).agg(
        n=('clicked', 'size'), y=('clicked', 'sum'))
    history = history.sort_values([entity, 'label_available_at'])
    history['history_n'] = history.groupby(entity).n.cumsum()
    history['history_y'] = history.groupby(entity).y.cumsum()
    query = frame[[entity, 'timestamp']].copy()
    query['_row'] = np.arange(len(query))
    joined = pd.merge_asof(query.sort_values('timestamp'),
        history.sort_values('label_available_at'), left_on='timestamp',
        right_on='label_available_at', by=entity, direction='backward', allow_exact_matches=False)
    joined = joined.sort_values('_row')
    result[f'{prefix}_history_impressions'] = joined.history_n.fillna(0).to_numpy()
    result[f'{prefix}_history_clicks'] = joined.history_y.fillna(0).to_numpy()
    result[f'{prefix}_history_ctr'] = (result[f'{prefix}_history_clicks'] + 20 * PRIOR) / (result[f'{prefix}_history_impressions'] + 20)
    return result


def build_features(frame):
    frame = frame.sort_values(['timestamp', 'impression_id']).reset_index(drop=True)
    for entity, prefix in [('campaign_id', 'campaign'), ('user_id', 'user')]:
        frame = add_history(frame, entity, prefix)
    return frame


class TemporalEncoder:
    """Day-block OOF encoding; a day's rows never encode their own labels.

    fit_transform is used for model training. transform uses only the fitted
    training outcomes and rejects rows before those outcomes became available.
    """
    def __init__(self, smoothing=20):
        self.smoothing = smoothing

    def fit_transform(self, frame):
        train = frame.copy().reset_index(drop=True)
        encoded = self._numeric(train)
        # Quantize availability upward: a day's encoding uses only outcomes
        # available strictly before the start of that day (conservative).
        for col in CATEGORICAL:
            events = train.groupby([col, 'label_available_at'], as_index=False).agg(
                n=('clicked', 'size'), y=('clicked', 'sum'))
            events = events.sort_values([col, 'label_available_at'])
            events['cn'] = events.groupby(col).n.cumsum()
            events['cy'] = events.groupby(col).y.cumsum()
            query = train[[col]].copy()
            query['cutoff'] = train.timestamp.dt.floor('D')
            query['_row'] = np.arange(len(train))
            found = pd.merge_asof(query.sort_values('cutoff'), events.sort_values('label_available_at'),
                left_on='cutoff', right_on='label_available_at', by=col,
                direction='backward', allow_exact_matches=False).sort_values('_row')
            encoded[col + '_te'] = ((found.cy.fillna(0) + self.smoothing * PRIOR) /
                                    (found.cn.fillna(0) + self.smoothing)).to_numpy()
        self.maps = {}
        for col in CATEGORICAL:
            stats = train.groupby(col).clicked.agg(['sum', 'count'])
            self.maps[col] = ((stats['sum'] + self.smoothing * PRIOR) /
                              (stats['count'] + self.smoothing)).to_dict()
        self.available_after = train.label_available_at.max()
        return encoded

    @staticmethod
    def _numeric(frame):
        return frame[NUMERIC].reset_index(drop=True).astype(float)

    def transform(self, frame):
        if len(frame) and frame.timestamp.min() <= self.available_after:
            raise ValueError('Encoder outcomes are not yet available at prediction time; purge the boundary')
        encoded = self._numeric(frame)
        for col in CATEGORICAL:
            encoded[col + '_te'] = frame[col].map(self.maps[col]).fillna(PRIOR).to_numpy()
        return encoded


def split_for_model(frame, config):
    """Fit, calibration-fit, validation, test; purge incomplete labels at boundaries."""
    splits = config['split']
    fit_end = pd.Timestamp(splits['fit_end_date']).normalize() + pd.Timedelta(days=1)
    train_end = pd.Timestamp(splits['train_end_date']).normalize() + pd.Timedelta(days=1)
    val_end = pd.Timestamp(splits['val_end_date']).normalize() + pd.Timedelta(days=1)
    if not fit_end < train_end < val_end:
        raise ValueError('Expected fit < train < validation date boundaries')
    ts, avail = frame.timestamp, frame.label_available_at
    parts = {
        'fit': frame[(ts < fit_end) & (avail < fit_end)],
        'calibration': frame[(ts >= fit_end) & (ts < train_end) & (avail < train_end)],
        'validation': frame[(ts >= train_end) & (ts < val_end) & (avail < val_end)],
        'test': frame[ts >= val_end],
    }
    if any(len(p) == 0 or p.clicked.nunique() < 2 for p in parts.values()):
        raise ValueError('Every model split needs observations of both classes; increase demo size')
    return {k: v.reset_index(drop=True) for k, v in parts.items()}
