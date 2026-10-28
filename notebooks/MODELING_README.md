# Current evaluation

`src/modeling.py` compares logistic regression and CatBoost using the same
17 features. Fit ends November 14, calibration-fit ends November 30, validation
ends December 15, and final test begins December 16, all in 2025 UTC. Each
pre-test window purges labels not fully available by its boundary.

Three forward-CV folds refit both model and temporal encoder. Platt scaling is
fitted on the separate calibration period. Raw versus calibrated candidates are
selected by validation log loss. Final test metrics are computed only after that
choice. No test labels select model, calibration or threshold.

The new demo selects calibrated logistic regression. Read `sample_reports/` for
measured results and the active generated `reports/current/` after a refresh.
The selected model's own explanation is exported: standardized coefficients
for logistic regression, or native CatBoost SHAP log-odds contributions for
CatBoost. Raw-model explanations do not explain the additional Platt mapping.

Historical features may update during validation and test only when earlier
outcomes have become available. This is an explicitly online evaluation, not a
frozen-history batch forecast. Statistical uncertainty is conditional on the
synthetic population and cannot establish real advertising performance.
