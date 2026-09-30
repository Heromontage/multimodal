"""
Pydantic schemas for CardioLens API
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class FeatureInput(BaseModel):
    """Input features for prediction"""
    features: Dict[str, Any] = Field(
        ...,
        example={
            "Age": 58,
            "Sex": "Male",
            "BP": 140,
            "PR": 78,
            "DM": 0,
            "HTN": 1,
            "Cholesterol": 250
        }
    )


class PredictionTarget(BaseModel):
    """Prediction result for a single target"""
    probability: float = Field(..., ge=0, le=1, example=0.87)
    label: int = Field(..., ge=0, le=1, example=1)
    threshold: float = Field(..., ge=0, le=1, example=0.46)


class ExplanationContribution(BaseModel):
    """SHAP contribution for a feature"""
    feature: str = Field(..., example="Typical Chest Pain")
    value: Any = Field(..., example=1)
    shap: float = Field(..., example=0.63)


class PredictionExplanation(BaseModel):
    """SHAP explanation for a target"""
    base_value: float = Field(..., example=-0.4)
    contributions: List[ExplanationContribution] = Field(default_factory=list)


class Measurement(BaseModel):
    """Clinical measurement with reference range"""
    feature: str = Field(..., example="BP")
    value: float = Field(..., example=140)
    unit: str = Field(..., example="mmHg")
    ref_range: List[float] = Field(..., example=[90, 120])
    status: str = Field(..., example="high")


class PredictionResponse(BaseModel):
    """Response from /predict endpoint"""
    model_version: str = Field(..., example="2026.1.0")
    predictions: Dict[str, PredictionTarget] = Field(...)
    explanations: Dict[str, PredictionExplanation] = Field(...)
    measurements: List[Measurement] = Field(default_factory=list)
    disclaimer: str = Field(
        ...,
        example="Decision support / educational use only. Not a substitute for formal diagnostic imaging."
    )


class SchemaResponse(BaseModel):
    """Response from /schema endpoint"""
    model_config = {"protected_namespaces": ()}
    schema: Dict[str, Any] = Field(
        ...,
        example={
            "Age": {
                "type": "int64",
                "min": 30,
                "max": 90,
                "default": 58,
                "unit": "years",
                "reference_range": [0, 120]
            }
        }
    )


class SamplesResponse(BaseModel):
    """Response from /samples endpoint"""
    samples: List[Dict[str, Any]] = Field(
        ...,
        example=[{
            "name": "High Risk Patient",
            "features": {
                "Age": 65,
                "Sex": "Male",
                "BP": 150,
                "PR": 80,
                "DM": 1,
                "HTN": 1
            }
        }]
    )


class MetricsResponse(BaseModel):
    """Response from /metrics endpoint"""
    model_version: str = Field(..., example="2026.1.0")
    evaluation: Dict[str, Any] = Field(default_factory=dict)
    feature_importance: Dict[str, Dict[str, float]] = Field(default_factory=dict)
