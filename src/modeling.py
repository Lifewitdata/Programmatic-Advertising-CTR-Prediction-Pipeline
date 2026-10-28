"""Forward validation, independently fitted calibration, and one final test.

The objective is validation log loss, with PR-AUC/ROC-AUC reported alongside.
Historical features update only from outcomes available at scoring time.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features import TemporalEncoder, split_for_model


def estimators(seed=42):
    return {
        'Logistic Regression': make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed)),
        'CatBoost': CatBoostClassifier(iterations=120, depth=4, learning_rate=0.05,
            loss_function='Logloss', random_seed=seed, thread_count=2,
            verbose=False, allow_writing_files=False),
    }


def metrics(y, probability):
    return {'roc_auc': float(roc_auc_score(y, probability)),
            'average_precision': float(average_precision_score(y, probability)),
            'log_loss': float(log_loss(y, probability, labels=[0, 1])),
            'brier': float(brier_score_loss(y, probability))}


def calibration_input(probability):
    return logit(np.clip(probability, 1e-6, 1 - 1e-6)).reshape(-1, 1)


def forward_cv(fit):
    """Refit encoders/models per fold; purge labels unavailable at fold start."""
    dates = np.array(sorted(fit.timestamp.dt.floor('D').unique()))
    records = []
    for fold, fraction in enumerate([0.45, 0.65, 0.80], 1):
        boundary = pd.Timestamp(dates[int(len(dates) * fraction)])
        end = boundary + pd.Timedelta(days=max(3, int(len(dates) * 0.15)))
        tr = fit[(fit.timestamp < boundary) & (fit.label_available_at < boundary)].reset_index(drop=True)
        va = fit[(fit.timestamp >= boundary) & (fit.timestamp < end)].reset_index(drop=True)
        if tr.clicked.nunique() < 2 or va.clicked.nunique() < 2:
            raise ValueError('Insufficient outcomes for forward CV')
        encoder = TemporalEncoder()
        xtr = encoder.fit_transform(tr)
        xva = encoder.transform(va)
        for name, model in estimators().items():
            model.fit(xtr, tr.clicked)
            records.append({'fold': fold, 'model': name, 'train_rows': len(tr),
                'validation_rows': len(va), 'validation_start': boundary.isoformat(),
                **metrics(va.clicked, model.predict_proba(xva)[:, 1])})
    return pd.DataFrame(records)


def train(frame, config, output='reports/current', artifacts='data/processed'):
    out, artifact_dir = Path(output), Path(artifacts)
    out.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    parts = split_for_model(frame, config)
    fit, cal, val, test = (parts[k] for k in ['fit', 'calibration', 'validation', 'test'])
    forward_cv(fit).to_csv(out / 'forward_cv.csv', index=False)
    encoder = TemporalEncoder()
    xfit = encoder.fit_transform(fit)
    xcal, xval, xtest = (encoder.transform(p) for p in [cal, val, test])
    candidates, rows = {}, []
    for name, model in estimators().items():
        model.fit(xfit, fit.clicked)
        pc = model.predict_proba(xcal)[:, 1]
        pv = model.predict_proba(xval)[:, 1]
        calibrator = LogisticRegression(C=1000, max_iter=500, random_state=42)
        calibrator.fit(calibration_input(pc), cal.clicked)
        calibrated = calibrator.predict_proba(calibration_input(pv))[:, 1]
        for method, probability in [('raw', pv), ('platt', calibrated)]:
            key = name + ' / ' + method
            rows.append({'candidate': key, **metrics(val.clicked, probability)})
            candidates[key] = (model, calibrator if method == 'platt' else None)
    comparison = pd.DataFrame(rows).sort_values(['log_loss', 'candidate']).reset_index(drop=True)
    comparison.to_csv(out / 'model_comparison_validation.csv', index=False)
    selected = comparison.iloc[0].candidate
    model, calibrator = candidates[selected]
    raw = model.predict_proba(xtest)[:, 1]
    probability = calibrator.predict_proba(calibration_input(raw))[:, 1] if calibrator is not None else raw
    # Test metrics are computed after candidate/calibration selection is frozen.
    summary = {'synthetic': True, 'generator_version': 2,
        'selected_model': selected, 'selection_metric': 'validation log_loss',
        'split_rows': {k: len(v) for k, v in parts.items()},
        'purged_rows': len(frame) - sum(len(p) for p in parts.values()),
        'test_prevalence': float(test.clicked.mean()),
        'test': metrics(test.clicked, probability),
        'test_raw': metrics(test.clicked, raw),
        'test_baseline': metrics(test.clicked, np.full(len(test), fit.clicked.mean())),
        'probability_status': 'Platt fitted on calibration only' if calibrator else 'Raw probabilities selected on validation',
        'history_protocol': 'Online outcomes after a complete 24h attribution window; strict prior timestamps',
        'feature_count': len(xfit.columns)}
    scored = test[['impression_id', 'advertiser_id', 'campaign_id', 'device', 'country', 'timestamp', 'clicked']].copy()
    scored['raw_probability'] = raw
    scored['probability'] = probability
    # Rank-based deciles are deterministic even when predictions are tied.
    scored['decile'] = pd.qcut(scored.probability.rank(method='first'), 10, labels=False) + 1
    deciles = scored.groupby('decile').agg(impressions=('clicked', 'size'), clicks=('clicked', 'sum'),
        predicted_ctr=('probability', 'mean'), raw_predicted_ctr=('raw_probability', 'mean')).reset_index()
    deciles['actual_ctr'] = deciles.clicks / deciles.impressions
    deciles['lift'] = deciles.actual_ctr / test.clicked.mean()
    deciles['scope'] = 'synthetic test set'
    deciles.to_csv(out / 'test_deciles.csv', index=False)
    summary['top_decile_lift'] = float(deciles.iloc[-1].lift)
    # Private, local row-level artifact; public exports contain aggregates only.
    scored.to_parquet(artifact_dir / 'test_scores.parquet', index=False)
    joblib.dump({'model': model, 'calibrator': calibrator, 'encoder': encoder,
                 'features': list(xfit.columns)}, artifact_dir / 'model_bundle.joblib')
    sample = xtest.iloc[:min(500, len(xtest))]
    if isinstance(model, CatBoostClassifier):
        shap_values = model.get_feature_importance(Pool(sample), type='ShapValues')
        importance = np.abs(shap_values[:, :-1]).mean(axis=0)
        explanation = 'Mean absolute SHAP contribution to raw CatBoost log odds; excludes Platt mapping'
    else:
        importance = model.named_steps['logisticregression'].coef_[0]
        explanation = 'Selected logistic regression coefficients per standardized feature; excludes Platt mapping'
    pd.DataFrame({'feature': xfit.columns, 'importance': importance, 'explanation': explanation,
                  'model': selected}).sort_values('importance', key=abs, ascending=False).to_csv(out / 'selected_model_explanation.csv', index=False)
    (out / 'model_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary
