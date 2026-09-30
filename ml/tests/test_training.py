from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cardiolens_ml.train import CardioLensTrainer


def test_reported_metrics_come_from_unseen_patients(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    trainer = CardioLensTrainer()
    trainer.config["model_candidates"] = ["logistic_regression"]
    trainer.config["cv"]["inner_splits"] = 2
    rng = np.random.default_rng(42)
    features = pd.DataFrame({"Age": rng.normal(55, 10, 60), "BP": rng.normal(130, 15, 60)})
    labels = pd.Series([0, 1] * 30)

    result = trainer.train_target("CAD", features, labels)

    assert result["metrics"]["source"] == "held_out"
    assert result["metrics"]["evaluation_samples"] == 12
    assert "cv_roc_auc_mean" in result["metrics"]
    assert "cv_roc_auc_std" in result["metrics"]
