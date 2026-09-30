"""
Pipeline builders for CardioLens models
"""
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
import yaml
import os
from pathlib import Path


def get_model(model_name: str, params: dict, calibrate: bool = False):
    """Get a model instance with optional calibration"""

    if model_name == "logistic_regression":
        model = LogisticRegression(**params)
    elif model_name == "random_forest":
        model = RandomForestClassifier(**params)
    elif model_name == "xgboost":
        model = XGBClassifier(**params)
    elif model_name == "lightgbm":
        model = LGBMClassifier(**params)
    else:
        raise ValueError(f"Unknown model: {model_name}")

    if calibrate:
        model = CalibratedClassifierCV(model, method='sigmoid', cv=5)

    return model


def create_model_pipeline(preprocessing_pipeline, model_name: str, model_params: dict,
                         calibrate: bool = False) -> Pipeline:
    """Create a full pipeline with preprocessing and model"""

    model = get_model(model_name, model_params, calibrate)

    pipeline = Pipeline([
        ('preprocessing', preprocessing_pipeline),
        ('classifier', model)
    ])

    return pipeline


def load_config(config_path: str = None):
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = str(Path(__file__).resolve().parents[2] / "config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def get_model_params(model_name: str, config: dict) -> dict:
    """Get model parameters from config"""
    return config['models'].get(model_name, {})


if __name__ == "__main__":
    # Test pipeline creation
    config = load_config()

    # Example preprocessing pipeline (would be created in data.py)
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    preprocessing = Pipeline([
        ('scaler', StandardScaler())
    ])

    # Create a logistic regression pipeline
    lr_params = get_model_params("logistic_regression", config)
    pipeline = create_model_pipeline(preprocessing, "logistic_regression", lr_params, calibrate=True)

    print("Pipeline created successfully:")
    print(pipeline)
