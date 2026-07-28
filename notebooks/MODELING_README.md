# Modeling — Phase 8

`notebooks/03_modeling.ipynb` — trains and compares 5 models, tunes and
cross-validates one in depth, runs SHAP analysis, and selects a final model
**programmatically from validation numbers**.

## Result

| Model | Val ROC-AUC | Val PR-AUC |
|---|---|---|
| **CatBoost (selected)** | **0.6066** | 0.0335 |
| Logistic Regression | 0.6034 | **0.0336** |
| LightGBM (tuned) | 0.5948 | 0.0320 |
| XGBoost | 0.5801 | 0.0287 |
| Random Forest | 0.5701 | 0.0276 |
| Baseline (constant CTR) | 0.5000 | 0.0220 |

CatBoost confirmed on the held-out test set: **ROC-AUC 0.6060** — matching
validation almost exactly, so this isn't a validation-set fluke.

Top test-decile lift: **1.81x** over baseline CTR (i.e., impressions the
model ranks in its top 10% click the actual users 1.81x more often than
random targeting would).

## Two things worth knowing before reading the notebook

**1. A real bug got caught and fixed, not glossed over.** LightGBM's early
stopping was silently tracking `binary_logloss` instead of ROC-AUC —
passing `eval_metric` to `.fit()` appends to LightGBM's default metric
rather than replacing it, and without `first_metric_only=True` on the
early-stopping callback, training stopped the moment logloss stopped
improving (round 1, under `scale_pos_weight`) even though validation AUC
kept climbing for ~40 more rounds. Diagnosed by logging both metrics
verbosely and watching them diverge, not by guessing. Fixed with
`metric="auc"` in the constructor + `first_metric_only=True`, applied
everywhere LightGBM appears in the notebook.

**2. The model that "should" win didn't, and the writeup says so.** Every
model — including plain Logistic Regression — lands in the same ~0.57-0.61
ROC-AUC band. Gradient-boosted trees don't clearly beat linear regression
here, which is unusual for tabular CTR data. Section 15/16 of the notebook
picks the winner from the actual numbers (CatBoost) rather than from which
model got the most tuning attention (LightGBM, which was tuned/CV'd/SHAP'd
specifically because it's fast enough to iterate on single-core — but
didn't end up winning). The likely explanation, laid out in the notebook:
the Phase 3 click-generation model's dominant driver is a per-user latent
propensity that's only partially recoverable through the
`user_historical_ctr` proxy, especially for low-history users — a real,
structural ceiling for this feature set, not a tuning failure.

## Files produced
- `notebooks/03_modeling.ipynb` / `.html` — full notebook, 56 cells, no errors
- `notebooks/figures/11-17_*.png` — ROC/PR curves, feature importance, SHAP
  summary + dependence plots, confusion matrix, calibration curve
- `data/processed/best_model.joblib` — the selected CatBoost model
- `data/processed/lightgbm_interpretability_demo.joblib` + `ordinal_encoder.joblib`
- `data/processed/model_comparison_val.csv` — full validation metric table
- `data/processed/model_selection_summary.json` — selection rationale + metrics

## Compute note
Single CPU core, ~4GB RAM. Training uses a 100,000-row stratified sample of
the 660,123-row training set (full val/test always used for evaluation).
The pipeline is otherwise unchanged and scales linearly to the full
training set on normal multi-core hardware.
