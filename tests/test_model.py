import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def api():
    assert importlib.util.find_spec('cardio_nb.model') is not None, 'Model implementation is missing'
    from cardio_nb import model
    return model


def sample():
    return pd.DataFrame({'Age': [40., 42., 45., 65., 70., 72.],
                         'Sex': ['Male', 'Fmale', 'Male', 'Fmale', 'Male', 'Fmale'],
                         'DM': [0, 0, 1, 1, 1, 0]}), np.array([0, 0, 0, 1, 1, 1])


def test_all_four_labels_are_excluded_and_original_labels_preserved():
    m = api()
    raw = pd.read_csv(Path(__file__).parents[1] / 'file.csv')
    x, y, audit = m.prepare_data(raw)
    assert not set(m.TARGETS).intersection(x.columns)
    assert x.shape == (303, 55)
    assert y['Cath'].sum() == 216
    assert audit['target_disagreement_count'] == 1


def test_invalid_targets_and_duplicate_patients_are_rejected():
    m = api()
    raw = pd.read_csv(Path(__file__).parents[1] / 'file.csv')
    with pytest.raises(ValueError, match='duplicate'):
        m.prepare_data(pd.concat([raw, raw.iloc[[0]]]))
    raw.loc[0, 'Cath'] = None
    with pytest.raises(ValueError, match='Cath'):
        m.prepare_data(raw)


@pytest.mark.parametrize('mode', ['gaussian', 'quantile', 'binned'])
def test_unseen_categories_missing_values_and_extremes_have_finite_probabilities(mode):
    m = api()
    x, y = sample()
    model = m.MixedNB(mode=mode, k='all').fit(x, y)
    new = pd.DataFrame({'Age': [None, 10000.], 'Sex': ['unknown', None], 'DM': [1, 0]})
    p = model.predict_proba(new)
    assert p.shape == (2, 2)
    assert np.isfinite(p).all()
    np.testing.assert_allclose(p.sum(axis=1), 1)
    assert model.predict_proba(x)[-1, 1] > model.predict_proba(x)[0, 1]


def test_preprocessing_is_fitted_only_on_training_and_schema_is_checked():
    m = api()
    x, y = sample()
    model = m.MixedNB().fit(x, y)
    before = model.predict_proba(x)
    extreme = x.copy()
    extreme['Age'] = 1e6
    model.predict_proba(extreme)
    np.testing.assert_allclose(before, model.predict_proba(x))
    with pytest.raises(ValueError, match='Missing'):
        model.predict_proba(x.drop(columns='Age'))
    with pytest.raises(ValueError, match='target'):
        model.fit(x.assign(Cath=y), y)


def test_nb_log_odds_match_hand_calculated_categorical_likelihoods():
    m = api()
    x = pd.DataFrame({'finding': ['yes', 'yes', 'no', 'yes', 'no', 'no']})
    y = np.array([1, 1, 1, 0, 0, 0])
    model = m.MixedNB(alpha=1, k='all').fit(x, y)
    # Both classes have equal size and prior; smoothed yes ratio is 3/2.
    assert model.decision_function(pd.DataFrame({'finding': ['yes']}))[0] == pytest.approx(np.log(1.5))


def test_serialization_and_feature_order_do_not_change_predictions(tmp_path):
    import joblib
    m = api()
    x, y = sample()
    model = m.MixedNB().fit(x, y)
    joblib.dump(model, tmp_path / 'model.joblib')
    loaded = joblib.load(tmp_path / 'model.joblib')
    np.testing.assert_allclose(model.predict_proba(x), loaded.predict_proba(x[x.columns[::-1]]))
