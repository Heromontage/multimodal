# Naive Bayes experiment plan

Build only the prediction and evaluation pipeline from ps.pdf and file.csv.
Predict Cath (CAD), LAD, LCX, and RCA independently; exclude all four from
every feature matrix. Preserve supplied labels, including the one disagreement.

1. Audit schema, class counts, missingness, duplicates, constants, and labels.
2. Implement mixed Naive Bayes: Gaussian continuous likelihoods (raw or
   quantile-normalized), or quantile bins; smoothed categorical likelihoods.
   Learn imputation, transformations, variance regularization, and feature
   selection only within the relevant training fold.
3. Freeze a modest candidate search before measuring results. Choose using
   inner stratified ROC-AUC. Compare against a fixed Gaussian NB baseline.
4. Evaluate with 5 outer folds repeated 3 times and 4 inner folds. No seed
   shopping, synthetic test examples, global feature selection, or label inputs.
5. Fit sigmoid probability calibration and a balanced-accuracy threshold using
   training-only out-of-fold scores. Outer-fold labels never inform tuning.
6. Save individual held-out predictions, folds, candidate scores, metrics,
   plots, dataset fingerprint, and trained full-data models. Report repeat
   variability and conditional patient-bootstrap uncertainty honestly.
7. Verify leakage exclusion, likelihood calculations, schema failures, unseen
   categories, missing values, serialization, and end-to-end prediction.

Primary endpoint: mean outer-fold ROC-AUC. Secondary: average precision,
accuracy, balanced accuracy, precision, recall, specificity, F1, Brier score,
and log loss. Threshold tuning trades these metrics off; it cannot improve AUC.
Final full-data model fitting is for future prediction and has no independent
test score. External validation remains necessary to establish transportability.
