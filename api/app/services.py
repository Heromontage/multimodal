"""
Services for CardioLens API
"""
import os
import joblib
import json
import numpy as np
import pandas as pd
import shap
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Canonical artifact paths
API_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parent

# Prefer ml/artifacts, fallback to root artifacts if present
DEFAULT_ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
if not DEFAULT_ARTIFACTS_DIR.exists() and (PROJECT_ROOT / "artifacts").exists():
    DEFAULT_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

artifacts_dir = Path(os.environ.get("ARTIFACTS_DIR", DEFAULT_ARTIFACTS_DIR))

# Shared state
models: Dict[str, Any] = {}
feature_schema: Optional[Dict[str, Any]] = None
shap_background: Optional[pd.DataFrame] = None
manifest: Dict[str, Any] = {}
metrics: Dict[str, Any] = {}
feature_importance: Dict[str, Dict[str, float]] = {}


def load_artifacts():
    """Load artifacts from artifacts_dir"""
    global models, feature_schema, shap_background, manifest, metrics, feature_importance

    models, feature_schema, shap_background, manifest, metrics, feature_importance = {}, None, None, {}, {}, {}

    logger.info(f"Loading CardioLens artifacts from {artifacts_dir}...")

    try:
        # Load feature schema
        schema_path = artifacts_dir / "schema.json"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                feature_schema = json.load(f)
            logger.info(f"Feature schema loaded with {len(feature_schema)} features")
        else:
            logger.warning(f"Feature schema not found at {schema_path}")

        # Load models for each target
        targets = ["CAD", "LAD", "LCX", "RCA"]
        for target in targets:
            model_path = artifacts_dir / "models" / f"{target}.joblib"
            if model_path.exists():
                models[target] = joblib.load(model_path)
                logger.info(f"Loaded {target} model from {model_path}")
            else:
                logger.info(f"Model for {target} not found at {model_path}")

        # Load SHAP background
        background_path = artifacts_dir / "shap_background.parquet"
        if background_path.exists():
            shap_background = pd.read_parquet(background_path)
            logger.info("SHAP background data loaded")

        # Load manifest
        manifest_path = artifacts_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            logger.info(f"Loaded manifest, version: {manifest.get('version', '1.0.0')}")

        # Load metrics
        for target in targets:
            target_metrics_path = artifacts_dir / f"{target}_metrics.json"
            if target_metrics_path.exists():
                with open(target_metrics_path, 'r') as f:
                    metrics[target] = json.load(f)
            importance_path = artifacts_dir / f"{target}_shap_importance.json"
            if importance_path.exists():
                with open(importance_path, 'r') as f:
                    feature_importance[target] = json.load(f)

    except Exception as e:
        logger.error(f"Error loading artifacts: {e}", exc_info=True)


def get_model_for_target(target: str):
    """Get loaded model for a specific target"""
    return models.get(target)


def get_all_models() -> Dict[str, Any]:
    """Get all loaded models"""
    return models


def get_feature_schema():
    """Get feature schema"""
    return feature_schema


def get_manifest():
    """Get loaded manifest"""
    return manifest


def get_all_metrics():
    """Get loaded metrics"""
    return metrics


def get_feature_importance():
    return feature_importance


def preprocess_input(input_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Preprocess and complete patient input for prediction.
    Fills missing features with schema defaults and converts types.
    """
    row: Dict[str, Any] = {}

    if feature_schema:
        for feat, info in feature_schema.items():
            if feat in input_dict and input_dict[feat] is not None:
                val = input_dict[feat]
                # Handle Sex string conversion
                if feat == "Sex" and isinstance(val, str):
                    val = 1 if val.strip().lower().startswith("m") else 0
                elif isinstance(val, (int, float)):
                    val = float(val)
                row[feat] = val
            else:
                # Use schema default if available, else 0
                row[feat] = info.get("default", 0.0)
    else:
        # Fallback if schema not loaded
        row = input_dict.copy()
        if "Sex" in row and isinstance(row["Sex"], str):
            row["Sex"] = 1 if row["Sex"].strip().lower().startswith("m") else 0

    return pd.DataFrame([row])


def validate_input(input_dict: Dict[str, Any]) -> None:
    """Reject fields that cannot be safely interpreted by the fitted models."""
    if feature_schema is None:
        raise ValueError("Feature schema is unavailable")
    forbidden = {'CAD', 'Cath', 'LAD', 'LCX', 'RCA'}
    unknown = set(input_dict) - set(feature_schema)
    if unknown & forbidden:
        raise ValueError(f"Target fields are not inputs: {', '.join(sorted(unknown & forbidden))}")
    if unknown:
        raise ValueError(f"Unknown features: {', '.join(sorted(unknown))}")
    for name, value in input_dict.items():
        if value is None:
            continue
        if name == 'Sex' and isinstance(value, str):
            if value.strip().lower() not in {'male', 'female', 'fmale'}:
                raise ValueError("Sex must be Male or Female")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        plausibility_bounds = {'Age': (0, 120), 'BP': (30, 300), 'PR': (20, 250)}
        if name in plausibility_bounds:
            low, high = plausibility_bounds[name]
            if not low <= value <= high:
                raise ValueError(f"{name} is outside the accepted input range")
        info = feature_schema[name]
        if (name == 'Sex' or (info.get('min') == 0 and info.get('max') == 1)) and value not in (0, 1):
            raise ValueError(f"{name} must be 0 or 1")


def predict_target(model, input_df: pd.DataFrame) -> Tuple[float, int, float]:
    """Get prediction probability, binary label, and decision threshold"""
    try:
        probability = float(model.predict_proba(input_df)[0, 1])
        threshold = 0.5
        label = 1 if probability >= threshold else 0
        return probability, label, threshold
    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        raise


def explain_prediction(model, input_df: pd.DataFrame) -> Dict[str, Any]:
    """Generate SHAP explanation for prediction"""
    try:
        if hasattr(model, 'named_steps'):
            preprocessor = model.named_steps.get('preprocessing')
            classifier = model.named_steps.get('classifier')
        else:
            preprocessor = None
            classifier = model

        # Transform input
        if preprocessor:
            input_transformed = preprocessor.transform(input_df)
            try:
                feature_names = list(preprocessor.get_feature_names_out(input_df.columns))
            except Exception:
                feature_names = list(input_df.columns)
        else:
            input_transformed = input_df.values
            feature_names = list(input_df.columns)

        # Extract fitted base estimator if calibrated
        if hasattr(classifier, 'calibrated_classifiers_') and len(classifier.calibrated_classifiers_) > 0:
            base_estimator = classifier.calibrated_classifiers_[0].estimator
        elif hasattr(classifier, 'estimator'):
            base_estimator = classifier.estimator
        else:
            base_estimator = classifier

        # Create appropriate explainer
        is_tree = any(tree_name in str(type(base_estimator)) for tree_name in ['XGB', 'LGBM', 'RandomForest', 'DecisionTree'])
        if is_tree:
            explainer = shap.TreeExplainer(base_estimator)
            shap_values = explainer.shap_values(input_transformed)
        else:
            bg = preprocessor.transform(shap_background) if shap_background is not None and preprocessor else input_transformed
            explainer = shap.LinearExplainer(base_estimator, bg)
            shap_values = explainer.shap_values(input_transformed)

        # Handle binary classification shapes
        if isinstance(shap_values, list):
            vals = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
        elif shap_values.ndim == 3:
            vals = shap_values[0, :, 1]
        elif len(shap_values.shape) > 1:
            vals = shap_values[0]
        else:
            vals = shap_values

        base_val = 0.0
        if hasattr(explainer, 'expected_value'):
            exp = explainer.expected_value
            if isinstance(exp, (list, np.ndarray)):
                base_val = float(exp[1] if len(exp) > 1 else exp[0])
            else:
                base_val = float(exp)

        contributions = []
        for i, feat in enumerate(feature_names[:len(vals)]):
            source_feature = feat.split('__', 1)[-1]
            contributions.append({
                "feature": feat,
                "value": float(input_df.iloc[0][source_feature]) if source_feature in input_df.columns else 0.0,
                "shap": float(vals[i])
            })

        # Sort by absolute impact
        contributions.sort(key=lambda x: abs(x["shap"]), reverse=True)

        return {
            "base_value": base_val,
            "contributions": contributions[:8]
        }

    except Exception as e:
        logger.warning(f"SHAP explanation unavailable: {e}")
        return {
            "base_value": 0.0,
            "contributions": []
        }


def get_measurements(input_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate clinical measurements with reference ranges"""
    measurements = []

    reference_ranges = {
        "Age": [0, 120, "years"],
        "Weight": [30, 200, "kg"],
        "Length": [140, 220, "cm"],
        "BMI": [15, 40, "kg/m²"],
        "BP": [90, 120, "mmHg"],
        "PR": [60, 100, "bpm"],
        "FBS": [70, 100, "mg/dL"],
        "BUN": [7, 20, "mg/dL"],
        "CR": [0.5, 1.2, "mg/dL"],
        "TG": [0, 150, "mg/dL"],
        "LDL": [0, 100, "mg/dL"],
        "HDL": [40, 60, "mg/dL"],
        "HB": [12, 18, "g/dL"],
        "K": [3.5, 5.0, "mmol/L"],
        "Na": [135, 145, "mmol/L"],
        "WBC": [4000, 11000, "/µL"],
        "PLT": [150, 400, "10³/µL"],
        "EF-TTE": [50, 75, "%"]
    }

    for feat, value in input_dict.items():
        if feat in reference_ranges and isinstance(value, (int, float)) and not pd.isna(value):
            low, high, unit = reference_ranges[feat]
            if value < low:
                status = "low"
            elif value > high:
                status = "high"
            else:
                status = "normal"

            measurements.append({
                "feature": feat,
                "value": float(value),
                "unit": unit,
                "ref_range": [low, high],
                "status": status
            })

    return measurements
