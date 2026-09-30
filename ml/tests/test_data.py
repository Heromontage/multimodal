from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cardiolens_ml.data import CardioLensDataProcessor
from cardiolens_ml.train import CardioLensTrainer


CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_clean_data_preserves_numeric_lab_measurements():
    processor = CardioLensDataProcessor(str(CONFIG))
    raw = pd.DataFrame({
        "Sex": ["Male", "Fmale"],
        "FBS": [90, 160],
        "CR": [0.7, 1.4],
        "LDL": [155, 121],
        "Obesity": ["Y", "N"],
        "Cath": ["Cad", "Normal"],
    })

    cleaned = processor.clean_data(raw)

    assert cleaned["FBS"].tolist() == [90, 160]
    assert cleaned["CR"].tolist() == [0.7, 1.4]
    assert cleaned["LDL"].tolist() == [155, 121]
    assert cleaned["Obesity"].tolist() == [1, 0]


def test_missing_vessel_target_is_reported_instead_of_invented():
    processor = CardioLensDataProcessor(str(CONFIG))
    data = pd.DataFrame({"Age": [53, 67], "Cath": ["Cad", "Normal"]})

    with pytest.raises(ValueError, match="LAD"):
        processor.prepare_features_targets(data, "LAD")


def test_all_target_columns_are_excluded_from_features():
    processor = CardioLensDataProcessor(str(CONFIG))
    data = pd.DataFrame({
        "Age": [53, 67], "Cath": ["Cad", "Normal"],
        "CAD": [1, 0], "LAD": ["Normal", "Stenosis"],
        "LCX": ["Normal", "Normal"], "RCA": ["Normal", "Normal"],
    })

    features, _ = processor.prepare_features_targets(data, "CAD")

    assert features.columns.tolist() == ["Age"]


def test_target_labels_match_vessel_labeled_dataset():
    processor = CardioLensDataProcessor(str(CONFIG))
    data = pd.DataFrame({
        "Age": [53, 67], "Cath": ["CAD", "Normal"],
        "LAD": ["Stenotic", "Normal"],
        "LCX": ["Normal", "Stenotic"],
        "RCA": ["Stenotic", "Normal"],
    })

    assert processor.prepare_features_targets(data, "CAD")[1].tolist() == [1, 0]
    assert processor.prepare_features_targets(data, "LAD")[1].tolist() == [1, 0]
    assert processor.prepare_features_targets(data, "LCX")[1].tolist() == [0, 1]
    assert processor.prepare_features_targets(data, "RCA")[1].tolist() == [1, 0]


def test_training_reads_vessel_labeled_file():
    trainer = CardioLensTrainer(str(CONFIG))
    data = trainer.load_and_prepare_data()

    assert len(data) == 303
    assert {"LAD", "LCX", "RCA"}.issubset(data.columns)
    assert set(trainer.targets) == {"CAD", "LAD", "LCX", "RCA"}
