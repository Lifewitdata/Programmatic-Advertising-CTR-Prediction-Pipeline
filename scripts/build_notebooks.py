"""Rebuild the three concise notebooks from the current, tested Python modules."""
from pathlib import Path
import nbformat as nbf

bootstrap = '''from pathlib import Path
import os, sys, json
import pandas as pd
import matplotlib.pyplot as plt
ROOT = Path.cwd()
if not (ROOT / 'src').exists():
    ROOT = ROOT.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
REPORTS = (ROOT / 'reports/current').resolve()
assert REPORTS.exists(), 'First run: python -m src.run_pipeline --n-impressions 25000'
plt.rcParams.update({'figure.dpi': 110, 'axes.spines.top': False, 'axes.spines.right': False})
'''


def write(name, cells):
    book = nbf.v4.new_notebook()
    book.metadata.kernelspec = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    book.cells = [nbf.v4.new_markdown_cell(c) if kind == 'md' else nbf.v4.new_code_cell(c) for kind, c in cells]
    nbf.write(book, Path('notebooks') / name)


write('eda.ipynb', [
    ('md', '# Advertising observations and data quality\n\nSynthetic generator version 2. Run the pipeline first. No revenue, causal lift or retention is inferred.'),
    ('code', bootstrap),
    ('code', "manifest = json.loads((REPORTS/'run_manifest.json').read_text())\nmanifest"),
    ('md', '## Reconcile source, prepared data and SQL reports\n\nBoth control differences must equal zero.'),
    ('code', "reconciliation = pd.read_csv(REPORTS/'reconciliation.csv')\nassert reconciliation.status.eq('MATCH').all()\nreconciliation"),
    ('code', "daily = pd.read_csv(REPORTS/'campaign_daily.csv', parse_dates=['event_date'])\ntrend = daily.groupby('event_date')[['impressions','clicks']].sum()\ntrend['ctr'] = trend.clicks/trend.impressions\ntrend.head()"),
    ('code', "fig, axes = plt.subplots(1,2,figsize=(12,4))\ntrend.impressions.plot(ax=axes[0], color='#243B55', title='Synthetic daily impressions')\n(trend.ctr*100).plot(ax=axes[1], color='#0B806B', title='Synthetic daily CTR (%)')\nplt.tight_layout(); plt.show()"),
    ('md', '## Segment uncertainty\n\nUser-cluster bootstrap intervals account for repeat impressions per user. Mobile-minus-desktop is an exploratory association; no randomized treatment or real-market population exists.'),
    ('code', "intervals = pd.read_csv(REPORTS/'device_intervals.csv')\nintervals"),
    ('code', "fig, ax=plt.subplots(figsize=(7,4))\nax.errorbar(intervals.device,intervals.ctr*100,yerr=[(intervals.ctr-intervals.ci_low)*100,(intervals.ci_high-intervals.ctr)*100],fmt='o',capsize=5,color='#0B806B')\nax.set_ylabel('CTR (%)'); ax.set_title('Synthetic device CTR and 95% user-cluster intervals')\nplt.tight_layout(); plt.show()"),
    ('code', "json.loads((REPORTS/'device_contrast.json').read_text())"),
    ('md', '## Decision\n\nCheck sample size and campaign objective before investigating low-CTR groups. Device associations reflect configured effects and confounding. See the decision memo for actions and constraints.'),
])
write('feature_engineering.ipynb', [
    ('md', '# Point-in-time feature engineering\n\nThis notebook uses the tested shared implementation. A complete 24-hour attribution window must close before an outcome enters history.'),
    ('code', bootstrap),
    ('code', "import yaml\nfrom src.features import labels, build_features, TemporalEncoder, split_for_model\nimpressions=pd.read_csv('data/raw/impressions.csv')\nclicks=pd.read_csv('data/raw/clicks.csv')\nmanifest=json.loads(Path('data/raw/manifest.json').read_text())\nconfig=yaml.safe_load(Path('config/etl_config.yaml').read_text())\nframe=build_features(labels(impressions,clicks,manifest['observed_through']))\nframe[['timestamp','label_available_at','campaign_history_impressions','campaign_history_ctr']].head()"),
    ('md', '## Purged chronological partitions\n\nConfigured end dates include the full day. Rows whose labels cross a boundary are excluded from the preceding partition.'),
    ('code', "parts=split_for_model(frame,config)\nfor left,right in [('fit','calibration'),('calibration','validation'),('validation','test')]:\n    assert parts[left].label_available_at.max()<parts[right].timestamp.min()\npd.DataFrame([{'split':k,'rows':len(v),'first':v.timestamp.min(),'last':v.timestamp.max()} for k,v in parts.items()])"),
    ('md', '## Chronological training encodings\n\nEach training day uses only outcomes available before that day. Separate CV folds instantiate separate encoders. Unknown categories receive a declared prior.'),
    ('code', "encoder=TemporalEncoder()\nxfit=encoder.fit_transform(parts['fit'])\nxval=encoder.transform(parts['validation'])\nassert 'click_propensity' not in xfit and 'clicked' not in xfit\nxfit.head()"),
    ('md', '## Leakage check by perturbation\n\nChanging outcomes from November onward must not change features for October impressions. Low correlation alone cannot establish this.'),
    ('code', "changed=frame.copy()\ncutoff=pd.Timestamp('2025-11-01')\nchanged.loc[changed.timestamp>=cutoff,'clicked']=1-changed.loc[changed.timestamp>=cutoff,'clicked']\nrebuilt=build_features(changed)\ncols=[c for c in frame if '_history_' in c]\npd.testing.assert_frame_equal(frame.loc[frame.timestamp<cutoff,cols],rebuilt.loc[rebuilt.timestamp<cutoff,cols])\nprint('Earlier history unchanged after perturbing future labels')"),
])
write('modeling.ipynb', [
    ('md', '# Model selection and calibrated probability evaluation\n\nFit, calibration-fit, validation selection and final test are separate chronological populations. The shared implementation is `src/modeling.py`.'),
    ('code', bootstrap),
    ('code', "summary=json.loads((REPORTS/'model_summary.json').read_text())\nsummary"),
    ('md', '## Forward CV\n\nEach fold refits its encoder and models. The purge ensures training outcomes exist before the fold starts. This table is not the final test.'),
    ('code', "pd.read_csv(REPORTS/'forward_cv.csv')"),
    ('md', '## Validation selection\n\nChoose model and raw/Platt variant using validation log loss. Platt parameters were fitted on the earlier calibration-fit population.'),
    ('code', "comparison=pd.read_csv(REPORTS/'model_comparison_validation.csv')\nassert comparison.sort_values(['log_loss','candidate']).iloc[0].candidate==summary['selected_model']\ncomparison"),
    ('md', '## Final test\n\nThe held-out test was not used for model or calibrator selection. Report baseline comparisons as well as ranking metrics.'),
    ('code', "pd.DataFrame({'selected':summary['test'],'raw_selected_model':summary['test_raw'],'constant_baseline':summary['test_baseline']})"),
    ('code', "deciles=pd.read_csv(REPORTS/'test_deciles.csv')\nfig,axes=plt.subplots(1,2,figsize=(11,4))\naxes[0].plot(deciles.predicted_ctr*100,deciles.actual_ctr*100,'o-',color='#0B806B')\nmaximum=max(deciles.predicted_ctr.max(),deciles.actual_ctr.max())*110\naxes[0].plot([0,maximum],[0,maximum],'--',color='#999999')\naxes[0].set(xlabel='Predicted CTR (%)',ylabel='Observed CTR (%)',title='Synthetic test calibration by decile')\naxes[1].bar(deciles.decile,deciles.lift,color='#243B55')\naxes[1].axhline(1,color='#999999',linestyle='--')\naxes[1].set(xlabel='Score decile (10 = highest)',ylabel='Observed lift',title='Synthetic retrospective ranking')\nplt.tight_layout(); plt.show()"),
    ('md', '## Explain the selected model\n\nExplanations belong to the selected raw model. A Platt mapping is an additional transformation and is not explained by raw-model coefficients or SHAP.'),
    ('code', "explanation=pd.read_csv(REPORTS/'selected_model_explanation.csv')\nassert explanation.model.eq(summary['selected_model']).all()\nexplanation.head(12)"),
    ('md', '## Interpretation\n\nThese results describe the generated population. Retrospective decile lift is not causal lift, incrementality or revenue. Review probability calibration and uncertainty before a real pilot. The previous version’s CatBoost/84-feature results are historical and superseded.'),
])
