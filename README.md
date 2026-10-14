# Coronary disease prediction with Naive Bayes

A fresh modeling-only implementation of the predictive requirements in `ps.pdf`.
A Next.js / React / TypeScript frontend now connects these saved models to an interactive BodyParts3D heart. The supplied `file.csv` remains unchanged.

Set up local database credentials with `python scripts/configure_database.py`, then start the complete app with `docker compose up --build`, then open http://localhost:3000. See [frontend setup and model routing](docs/frontend.md).

For a public HTTPS deployment of the frontend, backend, and MySQL on Oracle Cloud Always Free, see [deployment instructions](docs/deployment.md).

## Run

From the project directory, using the existing environment:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m cardio_nb.experiment --jobs 4
.venv/bin/python -m cardio_nb.predict --input new_patients.csv --output predictions.csv
```

To set up a new environment, use Python 3.11 (the tested version), create a virtual
environment, and install `requirements.txt`. Exact tested versions are also
recorded in `reports/manifest.json`. Training runs on CPU.

## Data and targets

303 rows, 55 input columns, and four binary targets. Positive classes are
`Cath=CAD`, and `LAD/LCX/RCA=Stenotic`. All four target columns are excluded
from **every** model's inputs. Do not derive CAD from vessel predictions or
replace the provided labels: one row has inconsistent overall/vessel labels.
Its CSV line is recorded in the audit. There are no missing cells or duplicate
feature rows in the supplied dataset. `Exertional CP` is constant and gets no
weight in the mixed models.

## Modeling and validation

- Fixed comparisons: ordinary Gaussian NB with training-fold preprocessing,
  and mixed NB with Gaussian continuous and smoothed categorical likelihoods.
- Tuned model: 48 predeclared configurations covering Gaussian, quantile-normal
  Gaussian, and quantile-binned continuous features; categorical smoothing;
  shared-variance shrinkage; and 10, 20, 35, or all informative features.
- Feature ranking uses absolute point-biserial correlation for continuous
  features and categorical association (correlation ratio) for discrete ones.
  Feature ranking, selection, binning, imputation, and scaling are fit afresh
  in each training fold. This is still Naive Bayes: feature likelihoods are
  multiplied conditionally on each class.
- Primary evaluation: **5-fold stratified outer CV repeated 3 times**, with
  **4-fold inner CV** selecting configurations by mean ROC-AUC. Seed 42 is
  fixed in advance; no seed or held-out-split selection. Each patient receives
  one held-out prediction per repeat for each target and method.
- The selected model's inner out-of-fold scores fit a regularized monotone
  sigmoid calibration and a threshold maximizing balanced accuracy. These
  operations use outer-training patients only. Inner calibration/threshold
  data also participate in hyperparameter selection; consequently their own
  scores are not unbiased estimates. The untouched outer folds assess the
  complete selection/calibration/threshold procedure.
- No oversampling, SMOTE, global feature selection, or synthetic test data.
  AUC is calculated from continuous NB scores, avoiding numerical ties from
  saturated probabilities. Calibration affects probability quality, and the
  threshold changes precision/recall; neither is advertised as an AUC boost.

The default experiment is frozen in `docs/experiment_plan.md`. Do not repeatedly
change it in response to the outer scores and continue calling those scores
unbiased. Any further development using these results requires fresh validation.

## Outputs

- `reports/results.md`: readable results and limitations.
- `reports/summary.csv`: mean outer-fold metrics, fold variability, repeat
  ranges, and a separate averaged held-out-prediction AUC.
- `reports/fold_metrics.csv`: all 180 method/target/fold evaluations, including
  accuracy, precision, recall, and F1 at the default 0.5 threshold for comparison.
- `reports/oof_predictions.csv`: individual held-out predictions and thresholds.
- `reports/inner_search.csv`: every inner search result.
- `reports/splits.json`: exact outer and inner patient indices, independently
  stratified per target. Row IDs are zero-based; CSV line numbers include header.
- `reports/manifest.json`: data fingerprint, audit, search space, configuration,
  and versions. `reports/validation.png`: ROC and calibration plots.
- `artifacts/{Cath,LAD,LCX,RCA}.joblib`: final full-data models, calibration,
  threshold, feature schema, and dataset fingerprint. Adjacent JSON files list
  selected parameters/features. These full-data fits have **no independent test
  score**; their inner selection scores must not be reported as test performance.

The fixed mixed NB alternatives are also saved under `artifacts/fixed`. Use
`--models artifacts/fixed` to predict with them; LCX had higher AUC with this
fixed alternative. See the report for the limits of choosing models from this
comparison.

## New patient inference

Use the original 55 feature headers and the same measurement units as `file.csv`.
Missing cells are supported (numeric training median; categorical missing token
or neutral unseen-category evidence), but missing columns fail clearly.
Unrecognized categorical values contribute neutral evidence, so check spelling
and source-data mappings; `Fmale` and `Female` are normalized identically.
Extra outcome columns, if present, are ignored. Input column order is irrelevant.
Output has row ID plus four probabilities and four binary predictions; `1`
means CAD/stenosis. Each outcome uses its own saved threshold.

The model's `feature_log_odds(frame)` method exposes exact additive feature
evidence before calibration. It describes model behavior, not causal effects.
Only load `.joblib` models from trusted sources.

## What these numbers establish

Repeated nested CV estimates performance on similar held-out patients. The
303-patient dataset cannot establish performance at a new hospital or on a
different population. Patient/site/time identifiers were not supplied, so
subject grouping or temporal/site validation is unavailable. Feature availability
at the intended prediction time must also be confirmed before deployment.

Bootstrap intervals resample patients' repeat-averaged held-out predictions;
they are conditional descriptive intervals, **not** uncertainty for the complete
retraining/selection process. Fold standard deviations are also not confidence
intervals, because training sets overlap. Averaged-prediction AUC is secondary
and need not equal mean outer-fold AUC. Predictions are research outputs, not
validated diagnostic probabilities. No guarantee of unseen-data performance
is possible from this dataset alone.

Methods references: [scikit-learn nested CV](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)
and [Naive Bayes likelihoods and probability limitations](https://scikit-learn.org/stable/modules/naive_bayes.html).
