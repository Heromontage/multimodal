import importlib.util
import pytest
import joblib
import numpy as np
import pandas as pd

from cardio_nb.model import MixedNB
from cardio_nb.experiment import ScoreCalibration


@pytest.mark.parametrize('calibrated', [True, False])
def test_saved_bundle_predicts_unlabeled_rows_and_ignores_supplied_outcomes(tmp_path, calibrated):
    assert importlib.util.find_spec('cardio_nb.predict') is not None, 'Prediction implementation is missing'
    from cardio_nb.predict import predict_frame
    x = pd.DataFrame({'Age': [35., 40., 45., 65., 70., 75.], 'DM': [0, 0, 1, 0, 1, 1]})
    y = np.array([0, 0, 0, 1, 1, 1])
    model = MixedNB().fit(x, y)
    calibration = ScoreCalibration().fit(model.decision_function(x), y)
    for target in ['Cath', 'LAD', 'LCX', 'RCA']:
        joblib.dump(dict(model=model, calibration=calibration if calibrated else None, threshold=.4,
                        features=x.columns.tolist(), target=target), tmp_path / f'{target}.joblib')
    a = predict_frame(x, tmp_path)
    b = predict_frame(x.assign(Cath='CAD', LAD='Normal', LCX='Stenotic', RCA='Normal'), tmp_path)
    pd.testing.assert_frame_equal(a, b)
    assert a.shape == (6, 9)
    assert a.CAD_probability.between(0, 1).all()
    assert a.CAD_prediction.tolist() == (a.CAD_probability >= .4).astype(int).tolist()


def test_entrypoint_calibration_can_be_exported_and_loaded_in_separate_processes(tmp_path):
    import subprocess
    import sys
    destination = str(tmp_path / "calibration.joblib")
    exporter = """
import runpy, joblib, numpy as np, sys
namespace = runpy.run_module("cardio_nb.experiment", run_name="experiment_entrypoint")
calibration = namespace["ScoreCalibration"]().fit(np.array([-2., -1., 1., 2.]), np.array([0, 0, 1, 1]))
joblib.dump(calibration, sys.argv[1])
"""
    exported = subprocess.run([sys.executable, "-c", exporter, destination], capture_output=True, text=True)
    assert exported.returncode == 0, exported.stderr
    imported = subprocess.run([sys.executable, "-c",
        "import joblib,sys; c=joblib.load(sys.argv[1]); assert c.predict([0]).shape == (1,)", destination],
        capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr
