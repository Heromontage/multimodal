"""Frozen-search repeated nested CV. Outer test labels are used only to score."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score, log_loss,
                             precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from .model import MixedNB, TARGETS, prepare_data
from .calibration import ScoreCalibration
from .report import export_fixed_models, write_report


def candidate_grid():
    result = []
    for mode, k, alpha, shrink in itertools.product(
            ['gaussian', 'quantile'], [10, 20, 35, 'all'], [1., 5.], [0., 1.]):
        result.append(dict(mode=mode, k=k, alpha=alpha, shrinkage=shrink))
    for k, alpha, bins in itertools.product([10, 20, 35, 'all'], [1., 5.], [3, 5]):
        result.append(dict(mode='binned', k=k, alpha=alpha, n_bins=bins))
    return result



def choose_threshold(y, p):
    fpr, tpr, thresholds = roc_curve(y, p)
    usable = np.isfinite(thresholds) & (thresholds >= 0) & (thresholds <= 1)
    thresholds, utility = thresholds[usable], (tpr-fpr)[usable]
    best = np.flatnonzero(np.isclose(utility, utility.max()))
    return float(thresholds[best[np.argmin(abs(thresholds[best]-.5))]])


def metrics(y, p, threshold=.5, ranking_score=None):
    pred = np.asarray(p) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    ranking_score = p if ranking_score is None else ranking_score
    return dict(roc_auc=float(roc_auc_score(y, ranking_score)),
                average_precision=float(average_precision_score(y, ranking_score)),
                accuracy=float(accuracy_score(y, pred)),
                balanced_accuracy=float(balanced_accuracy_score(y, pred)),
                precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)),
                specificity=float(tn/(tn+fp)), f1=float(f1_score(y, pred, zero_division=0)),
                brier=float(brier_score_loss(y, p)), log_loss=float(log_loss(y, p, labels=[0, 1])),
                tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp))


def gaussian_baseline(x):
    numeric = x.select_dtypes(include='number').columns.tolist()
    categorical = [c for c in x if c not in numeric]
    pre = ColumnTransformer([
        ('number', make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True),
                                 StandardScaler()), numeric),
        ('category', make_pipeline(SimpleImputer(strategy='most_frequent', keep_empty_features=True),
                                   OneHotEncoder(handle_unknown='ignore', sparse_output=False)), categorical)])
    return make_pipeline(pre, GaussianNB())


def _score_candidate(params, x, y, splits):
    scores, oof = [], np.empty(len(y))
    for train, valid in splits:
        model = MixedNB(**params).fit(x.iloc[train], y[train])
        out = model.decision_function(x.iloc[valid])
        oof[valid] = out
        scores.append(roc_auc_score(y[valid], out))
    return dict(params=params, mean_auc=float(np.mean(scores)),
                std_auc=float(np.std(scores, ddof=1)), oof=oof)


def tune(x, y, candidates, inner_splits, jobs):
    results = joblib.Parallel(n_jobs=jobs)(joblib.delayed(_score_candidate)(
        params, x, y, inner_splits) for params in candidates)
    # All candidates/search space are fixed before outer evaluation.
    best = max(results, key=lambda r: r['mean_auc'])
    calibrator = ScoreCalibration().fit(best['oof'], y)
    threshold = choose_threshold(y, calibrator.predict(best['oof']))
    fitted = MixedNB(**best['params']).fit(x, y)
    return fitted, calibrator, threshold, best, results


def evaluate_target(x, y, target, candidates, outer_folds=5, repeats=3,
                    inner_folds=4, seed=42, jobs=1):
    y = np.asarray(y)
    rows, fold_rows, searches, split_records = [], [], [], []
    for repeat in range(repeats):
        outer = StratifiedKFold(outer_folds, shuffle=True, random_state=seed+repeat)
        for fold, (train, test) in enumerate(outer.split(x, y)):
            xt, yt, xv = x.iloc[train], y[train], x.iloc[test]
            inner = list(StratifiedKFold(inner_folds, shuffle=True,
                         random_state=seed+1000+repeat*outer_folds+fold).split(xt, yt))
            split_records.append(dict(target=target, repeat=repeat, fold=fold,
                train_rows=train.tolist(), test_rows=test.tolist(),
                inner_splits=[dict(train_rows=train[a].tolist(), validation_rows=train[b].tolist())
                              for a, b in inner]))
            model, calibration, threshold, best, results = tune(xt, yt, candidates, inner, jobs)
            for r in results:
                searches.append(dict(target=target, repeat=repeat, fold=fold,
                                     params=json.dumps(r['params'], sort_keys=True),
                                     mean_auc=r['mean_auc'], std_auc=r['std_auc']))
            raw = model.decision_function(xv)
            variants = [('tuned_nb', calibration.predict(raw), raw, threshold)]
            fixed = MixedNB().fit(xt, yt)
            fixed_raw = fixed.decision_function(xv)
            variants.append(('fixed_mixed_nb', expit(fixed_raw), fixed_raw, .5))
            baseline = gaussian_baseline(xt).fit(xt, yt)
            lp = baseline.predict_log_proba(xv)
            baseline_raw = lp[:, 1]-lp[:, 0]
            variants.append(('gaussian_nb', baseline.predict_proba(xv)[:, 1], baseline_raw, .5))
            for name, p, score, cutoff in variants:
                result = metrics(y[test], p, cutoff, score)
                default = metrics(y[test], p, .5, score)
                fold_rows.append(dict(target=target, model=name, repeat=repeat, fold=fold,
                    threshold=cutoff, **result,
                    **{f'default_{k}': default[k] for k in ('accuracy', 'precision', 'recall', 'f1')}))
                for j, index in enumerate(test):
                    rows.append(dict(target=target, model=name, repeat=repeat, fold=fold,
                        row_id=int(index), csv_line=int(index+2), y_true=int(y[index]),
                        probability=float(p[j]), raw_score=float(score[j]), threshold=cutoff,
                        prediction=int(p[j] >= cutoff)))
            print(f'{target} repeat {repeat+1}/{repeats} fold {fold+1}/{outer_folds}: '
                  f'AUC={fold_rows[-3]["roc_auc"]:.3f}, params={best["params"]}', flush=True)
    return pd.DataFrame(rows), pd.DataFrame(fold_rows), searches, split_records


def bootstrap_auc(y, scores, seed=42, n_bootstrap=2000):
    """Conditional interval; does not refit models or quantify selection uncertainty."""
    rng = np.random.default_rng(seed)
    y, scores = np.asarray(y), np.asarray(scores)
    neg, pos = np.flatnonzero(y == 0), np.flatnonzero(y == 1)
    aucs = []
    for _ in range(n_bootstrap):
        idx = np.r_[rng.choice(neg, len(neg)), rng.choice(pos, len(pos))]
        aucs.append(roc_auc_score(y[idx], scores[idx]))
    return np.quantile(aucs, [.025, .975]).tolist()


def save_summary(predictions, folds, out):
    measures = ['roc_auc', 'average_precision', 'accuracy', 'balanced_accuracy',
                'precision', 'recall', 'specificity', 'f1', 'brier', 'log_loss']
    rows = []
    for (target, name), group in folds.groupby(['target', 'model'], sort=False):
        pred = predictions[(predictions.target == target) & (predictions.model == name)]
        avg = pred.groupby('row_id').agg(y_true=('y_true', 'first'),
                    probability=('probability', 'mean'), raw_score=('raw_score', 'mean'))
        score = avg.probability if name == 'tuned_nb' else avg.raw_score
        interval = bootstrap_auc(avg.y_true, score)
        row = dict(target=target, model=name,
                   **{f'{m}_mean': float(group[m].mean()) for m in measures},
                   roc_auc_fold_sd=float(group.roc_auc.std()),
                   averaged_oof_auc=float(roc_auc_score(avg.y_true, score)),
                   conditional_ci_low=interval[0], conditional_ci_high=interval[1],
                   repeat_auc_min=float(group.groupby('repeat').roc_auc.mean().min()),
                   repeat_auc_max=float(group.groupby('repeat').roc_auc.mean().max()))
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary.to_csv(out / 'summary.csv', index=False)
    return summary


def make_plots(predictions, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve
    fig, axes = plt.subplots(2, 4, figsize=(17, 8))
    for i, target in enumerate(TARGETS):
        for name, color in [('gaussian_nb', '#aaaaaa'), ('fixed_mixed_nb', '#c88732'),
                            ('tuned_nb', '#127784')]:
            subset = predictions[(predictions.target == target) & (predictions.model == name)]
            avg = subset.groupby('row_id')[['y_true', 'probability', 'raw_score']].mean()
            score = avg.probability if name == 'tuned_nb' else avg.raw_score
            fpr, tpr, _ = roc_curve(avg.y_true, score)
            auc = roc_auc_score(avg.y_true, score)
            axes[0, i].plot(fpr, tpr, label=f'{name}: {auc:.3f}', color=color)
        tuned = predictions[(predictions.target == target) & (predictions.model == 'tuned_nb')]
        avg = tuned.groupby('row_id')[['y_true', 'probability']].mean()
        frac, mean = calibration_curve(avg.y_true, avg.probability, n_bins=5, strategy='quantile')
        axes[1, i].plot(mean, frac, 'o-', color='#127784')
        for ax in axes[:, i]:
            ax.plot([0, 1], [0, 1], '--', color='#bbbbbb', linewidth=1)
            ax.set(xlim=(0, 1), ylim=(0, 1))
            ax.grid(alpha=.15)
        axes[0, i].set(title='CAD' if target == 'Cath' else target,
                       xlabel='False positive rate', ylabel='True positive rate')
        axes[0, i].legend(fontsize=8, loc='lower right')
        axes[1, i].set(xlabel='Mean predicted probability', ylabel='Observed positive fraction')
    fig.suptitle('Repeated held-out predictions averaged per patient\n'
                 'Descriptive ROC and calibration plots; primary results are mean outer-fold AUC', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .92))
    fig.savefig(out / 'validation.png', dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='file.csv')
    parser.add_argument('--output', default='reports')
    parser.add_argument('--models', default='artifacts')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--outer-folds', type=int, default=5)
    parser.add_argument('--inner-folds', type=int, default=4)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    out, models = Path(args.output), Path(args.models)
    out.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    x, y, audit = prepare_data(pd.read_csv(args.data))
    candidates = candidate_grid()
    manifest = dict(configuration=vars(args), dataset_sha256=hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        audit=audit, candidates=candidates, versions=dict(python=platform.python_version(),
        sklearn=sklearn.__version__, pandas=pd.__version__, numpy=np.__version__, scipy=scipy.__version__),
        evaluation='Repeated nested stratified CV; all tuning uses outer-training data only',
        caveat='No external test cohort. Bootstrap intervals condition on fitted OOF predictions; not full uncertainty.')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    all_predictions, all_folds, all_searches, all_splits = [], [], [], []
    with threadpool_limits(limits=1), joblib.parallel_config(backend='loky', inner_max_num_threads=1):
        for target in TARGETS:
            predictions, folds, searches, splits = evaluate_target(x, y[target].to_numpy(), target,
                candidates, args.outer_folds, args.repeats, args.inner_folds, args.seed, args.jobs)
            all_predictions.append(predictions)
            all_folds.append(folds)
            all_searches.extend(searches)
            all_splits.extend(splits)
            # Incremental persistence, without using outer scores to change the experiment.
            pd.concat(all_predictions).to_csv(out / 'oof_predictions.csv', index=False)
            pd.concat(all_folds).to_csv(out / 'fold_metrics.csv', index=False)
            pd.DataFrame(all_searches).to_csv(out / 'inner_search.csv', index=False)
            (out / 'splits.json').write_text(json.dumps(all_splits))
            inner = list(StratifiedKFold(args.inner_folds, shuffle=True,
                        random_state=args.seed+2000).split(x, y[target]))
            model, calibration, threshold, best, results = tune(x, y[target].to_numpy(), candidates, inner, args.jobs)
            bundle = dict(model=model, calibration=calibration, threshold=threshold,
                target=target, positive_label='CAD' if target == 'Cath' else 'Stenotic',
                features=x.columns.tolist(), dataset_sha256=manifest['dataset_sha256'])
            joblib.dump(bundle, models / f'{target}.joblib')
            metadata = dict(target=target, params=best['params'], threshold=threshold,
                calibration_slope=float(calibration.slope_),
                selected_features=model.selected_features_,
                inner_selection_auc=best['mean_auc'],
                note='Inner selection score is optimistic; see nested outer-fold metrics for evaluation.')
            (models / f'{target}.json').write_text(json.dumps(metadata, indent=2))
            pd.DataFrame([{k: v for k, v in r.items() if k != 'oof'} for r in results]).to_csv(
                out / f'{target}_final_search.csv', index=False)
    predictions, folds = pd.concat(all_predictions), pd.concat(all_folds)
    summary = save_summary(predictions, folds, out)
    make_plots(predictions, out)
    export_fixed_models(x, y, models, manifest['dataset_sha256'])
    write_report(out)
    print(summary[['target', 'model', 'roc_auc_mean', 'accuracy_mean', 'f1_mean']].to_string(index=False))


if __name__ == '__main__':
    main()
