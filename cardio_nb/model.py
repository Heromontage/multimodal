"""Small-sample mixed likelihood Naive Bayes; every statistic is fit locally."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import QuantileTransformer, StandardScaler
from sklearn.utils.validation import check_is_fitted

TARGETS = ('Cath', 'LAD', 'LCX', 'RCA')
CONTINUOUS = ('Age', 'Weight', 'Length', 'BMI', 'BP', 'PR', 'FBS', 'CR',
              'TG', 'LDL', 'HDL', 'BUN', 'ESR', 'HB', 'K', 'Na', 'WBC',
              'Lymph', 'Neut', 'PLT', 'EF-TTE')


def prepare_data(raw):
    """Keep supplied outcomes; fail rather than allow duplicates across folds."""
    if raw.columns.duplicated().any():
        raise ValueError('Duplicate column names')
    for c in TARGETS:
        allowed = {'CAD', 'Normal'} if c == 'Cath' else {'Stenotic', 'Normal'}
        if c not in raw or not raw[c].isin(allowed).all():
            raise ValueError(f'Invalid or missing target labels: {c}')
    x = raw.drop(columns=list(TARGETS)).copy()
    if x.duplicated().any():
        raise ValueError('Found duplicate feature rows; resolve patient identities before CV')
    y = pd.DataFrame({c: raw[c].eq('CAD' if c == 'Cath' else 'Stenotic').astype(int)
                      for c in TARGETS})
    mismatch = y.Cath.ne(y[['LAD', 'LCX', 'RCA']].any(axis=1).astype(int))
    audit = {'rows': len(raw), 'input_features': len(x.columns),
             'missing_cells': int(x.isna().sum().sum()),
             'duplicate_feature_rows': int(x.duplicated().sum()),
             'constant_features': x.columns[x.nunique(dropna=False) <= 1].tolist(),
             'positive_counts': {c: int(y[c].sum()) for c in TARGETS},
             'target_disagreement_count': int(mismatch.sum()),
             'target_disagreement_csv_lines': (np.flatnonzero(mismatch) + 2).tolist()}
    return x.reset_index(drop=True), y.reset_index(drop=True), audit


def _category(value):
    if pd.isna(value):
        return '__missing__'
    if isinstance(value, (int, float, np.number)):
        return str(float(value))
    value = str(value).strip().lower()
    return 'female' if value == 'fmale' else value


class MixedNB(ClassifierMixin, BaseEstimator):
    """Gaussian/quantile/binned numeric + Laplace-smoothed categorical NB.

    k selects whole original features using within-training association scores.
    shrinkage pulls each class variance toward the shared within-class variance.
    Unknown categories carry neutral evidence. There are no label-derived inputs.
    """

    def __init__(self, mode='gaussian', alpha=1., shrinkage=0.5, k='all',
                 n_bins=4, variance_floor=0.05):
        self.mode = mode
        self.alpha = alpha
        self.shrinkage = shrinkage
        self.k = k
        self.n_bins = n_bins
        self.variance_floor = variance_floor

    def _frame(self, x):
        if not isinstance(x, pd.DataFrame):
            raise ValueError('Expected a DataFrame with named clinical features')
        missing = set(self.feature_names_in_) - set(x.columns)
        if missing:
            raise ValueError(f'Missing required features: {sorted(missing)}')
        return x.loc[:, self.feature_names_in_]

    def fit(self, X, y):
        if not isinstance(X, pd.DataFrame) or X.columns.duplicated().any():
            raise ValueError('Expected uniquely named DataFrame features')
        if set(TARGETS).intersection(X.columns):
            raise ValueError('Forbidden target column present in features')
        if self.mode not in ('gaussian', 'quantile', 'binned'):
            raise ValueError('Unknown likelihood mode')
        if self.alpha <= 0 or not 0 <= self.shrinkage <= 1 or self.variance_floor <= 0:
            raise ValueError('Invalid smoothing parameters')
        y = np.asarray(y, dtype=int)
        if len(X) != len(y) or set(np.unique(y)) != {0, 1}:
            raise ValueError('Training requires both binary classes')
        self.classes_ = np.array([0, 1])
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        counts = np.bincount(y)
        self.prior_log_odds_ = float(np.log(counts[1] / counts[0]))
        self.numeric_ = [c for c in X if c in CONTINUOUS]
        self.categorical_ = [c for c in X if c not in CONTINUOUS]
        numeric = X[self.numeric_].apply(pd.to_numeric, errors='raise').to_numpy(dtype=float, copy=True)
        numeric[~np.isfinite(numeric)] = np.nan
        self.medians_ = np.array([np.nanmedian(a) if np.isfinite(a).any() else 0.
                                  for a in numeric.T])
        numeric = np.where(np.isnan(numeric), self.medians_, numeric)
        self.transform_ = None
        if len(self.numeric_):
            self.transform_ = (QuantileTransformer(n_quantiles=min(50, len(X)),
                                output_distribution='normal', random_state=42)
                               if self.mode == 'quantile' else StandardScaler())
            numeric = self.transform_.fit_transform(numeric)
        self.edges_ = {}
        self.cat_maps_ = {}
        self.cat_log_odds_ = {}
        self.numeric_params_ = {}
        self.associations_ = {}
        for j, c in enumerate(self.numeric_):
            a = numeric[:, j]
            if self.mode == 'binned':
                self.edges_[c] = np.unique(np.quantile(a, np.linspace(0, 1, self.n_bins+1)[1:-1]))
                codes = np.searchsorted(self.edges_[c], a, side='right')
                self._fit_categories(c, codes, y, counts, len(self.edges_[c])+1)
            else:
                means = np.array([a[y == z].mean() for z in (0, 1)])
                variances = np.array([a[y == z].var() for z in (0, 1)])
                pooled = np.average(variances, weights=counts)
                variances = ((1-self.shrinkage)*variances + self.shrinkage*pooled)
                variances = np.maximum(variances, self.variance_floor)
                self.numeric_params_[c] = (means, variances)
                self.associations_[c] = (abs(float(np.corrcoef(a, y)[0, 1]))
                                          if a.std() > 1e-12 else 0.)
        for c in self.categorical_:
            values = X[c].map(_category)
            self.cat_maps_[c] = {v: i for i, v in enumerate(sorted(values.unique()))}
            codes = values.map(self.cat_maps_[c]).to_numpy()
            self._fit_categories(c, codes, y, counts, len(self.cat_maps_[c]))
        ranked = sorted(self.associations_, key=lambda c: -self.associations_[c])
        ranked = [c for c in ranked if self.associations_[c] > 1e-12]
        self.selected_features_ = ranked if self.k == 'all' else ranked[:int(self.k)]
        return self

    def _fit_categories(self, name, codes, y, counts, n_categories):
        table = np.array([np.bincount(codes[y == z], minlength=n_categories) for z in (0, 1)])
        logp = np.log((table+self.alpha)/(counts[:, None]+self.alpha*n_categories))
        self.cat_log_odds_[name] = logp[1]-logp[0]
        totals = table.sum(axis=0)
        rates = np.divide(table[1], totals, out=np.zeros(n_categories), where=totals > 0)
        self.associations_[name] = float(np.sqrt(np.sum(totals*(rates-y.mean())**2)
                                                        / (len(y)*y.mean()*(1-y.mean()))))

    def feature_log_odds(self, X):
        check_is_fitted(self, 'selected_features_')
        X = self._frame(X)
        numeric = X[self.numeric_].apply(pd.to_numeric, errors='raise').to_numpy(dtype=float, copy=True)
        numeric[~np.isfinite(numeric)] = np.nan
        numeric = np.where(np.isnan(numeric), self.medians_, numeric)
        if self.transform_ is not None:
            numeric = self.transform_.transform(numeric)
        evidence = {}
        for c in self.selected_features_:
            if c in self.numeric_:
                a = numeric[:, self.numeric_.index(c)]
                if self.mode == 'binned':
                    codes = np.searchsorted(self.edges_[c], a, side='right')
                    evidence[c] = self.cat_log_odds_[c][codes]
                else:
                    means, variances = self.numeric_params_[c]
                    logp = -.5*(np.log(variances)[None, :]+(a[:, None]-means)**2/variances)
                    evidence[c] = logp[:, 1]-logp[:, 0]
            else:
                codes = X[c].map(_category).map(self.cat_maps_[c]).fillna(-1).to_numpy(dtype=int)
                odds = self.cat_log_odds_[c]
                evidence[c] = np.where(codes >= 0, odds[np.maximum(codes, 0)], 0.)
        return pd.DataFrame(evidence, index=X.index)

    def decision_function(self, X):
        return self.prior_log_odds_ + self.feature_log_odds(X).sum(axis=1).to_numpy()

    def predict_proba(self, X):
        p = expit(self.decision_function(X))
        return np.column_stack([1-p, p])

    def predict(self, X):
        return (self.decision_function(X) >= 0).astype(int)
