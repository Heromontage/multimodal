"""Render an experiment report from saved measurements, without retuning."""
from pathlib import Path
import json

import joblib
import pandas as pd

from .model import MixedNB, TARGETS


def export_fixed_models(x, y, models, fingerprint):
    out = Path(models) / 'fixed'
    out.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        model = MixedNB().fit(x, y[target].to_numpy())
        joblib.dump(dict(model=model, calibration=None, threshold=.5, target=target,
            positive_label='CAD' if target == 'Cath' else 'Stenotic', features=x.columns.tolist(),
            dataset_sha256=fingerprint), out / f'{target}.joblib')
        (out / f'{target}.json').write_text(json.dumps(dict(params=model.get_params(),
            threshold=.5, selected_features=model.selected_features_,
            note='Fixed mixed NB baseline; uncalibrated probabilities.'), indent=2))


def write_report(out):
    out = Path(out)
    summary = pd.read_csv(out / 'summary.csv')
    folds = pd.read_csv(out / 'fold_metrics.csv')
    manifest = json.loads((out / 'manifest.json').read_text())
    lines = ['# Naive Bayes results', '',
        '303 patients; four independently modeled outcomes; no web application.', '',
        '## Primary ROC-AUC comparison', '',
        'Mean of 15 held-out outer folds (5 folds × 3 repeats). Tuned configurations',
        'are selected by 4-fold inner CV. Standard deviations describe variation',
        'across folds, not confidence intervals.', '',
        '| Target | Gaussian NB | Fixed mixed NB | Tuned mixed NB | Tuned fold SD |',
        '|---|---:|---:|---:|---:|']
    for target in TARGETS:
        g = summary[summary.target == target].set_index('model')
        lines.append(f'| {"CAD" if target == "Cath" else target} | '
            f'{g.loc["gaussian_nb", "roc_auc_mean"]:.4f} | '
            f'{g.loc["fixed_mixed_nb", "roc_auc_mean"]:.4f} | '
            f'{g.loc["tuned_nb", "roc_auc_mean"]:.4f} | '
            f'{g.loc["tuned_nb", "roc_auc_fold_sd"]:.4f} |')
    lines += ['', 'Tuning improved the observed mean AUC for CAD, LAD, and RCA, but harmed LCX.',
        'The fixed LCX model had the stronger observed ranking performance. Both',
        'variants are saved; the default inference folder contains the tuned models.',
        'Use `--models artifacts/fixed` for fixed mixed NB. A preference for fixed LCX',
        'based on this comparison is exploratory: selecting a method on outer results',
        'does not produce an unbiased estimate of a newly combined selection strategy.',
        'The small LAD/RCA differences do not establish statistical superiority.', '',
        '## Tuned models: threshold trade-offs', '',
        'The saved thresholds maximize balanced accuracy on training-only cross-fitted',
        'predictions. They do not maximize every metric simultaneously.', '',
        '| Target | Accuracy | Precision | Recall | Specificity | F1 | Balanced accuracy |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for target in TARGETS:
        r = summary[(summary.target == target) & (summary.model == 'tuned_nb')].iloc[0]
        vals = ' | '.join(f'{r[m+"_mean"]:.4f}' for m in
                         ['accuracy', 'precision', 'recall', 'specificity', 'f1', 'balanced_accuracy'])
        lines.append(f'| {"CAD" if target == "Cath" else target} | {vals} |')
    lines += ['', 'At the conventional 0.5 probability threshold:', '',
        '| Target | Accuracy | Precision | Recall | F1 |', '|---|---:|---:|---:|---:|']
    for target, r in folds[folds.model == 'tuned_nb'].groupby('target'):
        values = ' | '.join(f'{r["default_"+m].mean():.4f}' for m in ['accuracy', 'precision', 'recall', 'f1'])
        lines.append(f'| {"CAD" if target == "Cath" else target} | {values} |')
    lines += ['', 'ROC-AUC is unchanged by the classification threshold. For CAD, 0.5',
        'gives higher accuracy/F1 and recall, while the tuned threshold favors',
        'specificity and balanced accuracy. Vessel thresholds generally recover',
        'more positives at the expense of specificity.', '',
        '## Ranking, probability quality, and uncertainty', '',
        '| Target | Average precision | Brier (lower better) | Log loss (lower better) | Repeat mean AUC range |',
        '|---|---:|---:|---:|---:|']
    for target in TARGETS:
        r = summary[(summary.target == target) & (summary.model == 'tuned_nb')].iloc[0]
        lines.append(f'| {"CAD" if target == "Cath" else target} | {r.average_precision_mean:.4f} | '
            f'{r.brier_mean:.4f} | {r.log_loss_mean:.4f} | {r.repeat_auc_min:.4f}–{r.repeat_auc_max:.4f} |')
    lines += ['', 'The calibrated tuned systems have lower Brier/log loss than the fixed',
        'uncalibrated comparisons. This evaluates the whole system; it does not isolate',
        'calibration from model changes. A naive classifier predicting observed class',
        'prevalence has expected ROC-AUC 0.5; average precision should be interpreted',
        'relative to each target prevalence.', '',
        '![ROC and calibration plots](validation.png)', '',
        'The figure averages three held-out predictions per patient; its AUC values',
        'are secondary descriptive measures and differ from the primary fold means.',
        'Conditional patient-bootstrap intervals are in `summary.csv`. They keep',
        'fitted predictions fixed and omit retraining/model-selection uncertainty.', '',
        '## Audit and validation limits', '',
        f'- Positive counts: {manifest["audit"]["positive_counts"]}.',
        f'- Supplied CAD/vessel disagreement occurs at CSV line(s) {manifest["audit"]["target_disagreement_csv_lines"]}; labels were preserved.',
        '- All Cath/LAD/LCX/RCA columns are excluded from every model input.',
        '- No missing values or duplicate feature rows in the supplied data.',
        '- Missing values, unseen categorical values, feature selection, scaling, and bins are handled within training folds.',
        '- Raw Gaussian NB can be badly miscalibrated for rare binary findings; this explains poor threshold metrics despite useful ranking.',
        '- No independent external cohort or patient/site/time identifiers were supplied.',
        '- LCX/RCA discrimination is modest. More data and external validation are needed before claiming reliable generalization.',
        '- Final saved models are trained on all 303 rows and have no independent test score.',
        '- No result proves a global maximum ROC-AUC or guarantees performance on new populations.', '',
        'Full search settings and exact package versions are in `manifest.json`;',
        'individual predictions, metrics, and splits are retained for audit.', '',
        'Method references: [nested cross-validation](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)',
        'and [Naive Bayes](https://scikit-learn.org/stable/modules/naive_bayes.html).', '']
    (out / 'results.md').write_text('\n'.join(lines))
