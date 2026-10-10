import importlib.util
import numpy as np
import pandas as pd


def api():
    assert importlib.util.find_spec('cardio_nb.experiment') is not None, 'Experiment implementation is missing'
    from cardio_nb import experiment
    return experiment


def test_outer_predictions_cover_each_patient_once_and_never_train_on_test_rows():
    e = api()
    rng = np.random.default_rng(7)
    x = pd.DataFrame({'Age': rng.normal(60, 10, 40), 'DM': rng.integers(0, 2, 40)})
    y = np.tile([0, 1], 20)
    candidates = [{'mode': 'gaussian', 'k': 'all', 'alpha': 1.}]
    predictions, folds, searches, splits = e.evaluate_target(
        x, y, 'test', candidates, outer_folds=2, repeats=1, inner_folds=2, seed=42, jobs=1)
    tuned = predictions[predictions.model == 'tuned_nb']
    assert sorted(tuned.row_id.tolist()) == list(range(40))
    assert np.isfinite(tuned.probability).all()
    assert len(folds) == 6
    for split in splits:
        assert not set(split['train_rows']) & set(split['test_rows'])
        for inner in split['inner_splits']:
            assert set(inner['train_rows']).issubset(split['train_rows'])
            assert set(inner['validation_rows']).issubset(split['train_rows'])
            assert not set(inner['train_rows']) & set(inner['validation_rows'])


def test_balanced_threshold_and_probability_calibration():
    e = api()
    y = np.array([0, 0, 1, 1])
    p = np.array([.1, .2, .3, .4])
    threshold = e.choose_threshold(y, p)
    assert .2 < threshold <= .3
    calibrated = e.ScoreCalibration().fit(np.array([-2., -1., 1., 2.]), y)
    output = calibrated.predict(np.array([-3., 0., 3.]))
    assert 0 < output[0] < output[1] < output[2] < 1


def test_roc_auc_uses_ranking_not_binary_predictions():
    e = api()
    result = e.metrics(np.array([0, 0, 1, 1]), np.array([.1, .2, .3, .4]), .5)
    assert result['roc_auc'] == 1.
    assert result['accuracy'] == .5
