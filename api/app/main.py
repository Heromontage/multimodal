"""
Main FastAPI application for CardioLens
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pandas as pd
from pathlib import Path
import logging
import os
from ml.src.cardiolens_ml.data import CardioLensDataProcessor

from .schemas import (
    FeatureInput, PredictionResponse,
    SchemaResponse, MetricsResponse, SamplesResponse
)
from .services import (
    load_artifacts,
    get_model_for_target,
    get_all_models,
    get_feature_schema,
    get_manifest,
    get_all_metrics,
    get_feature_importance,
    preprocess_input,
    validate_input,
    predict_target,
    explain_prediction,
    get_measurements,
    PROJECT_ROOT
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
REQUIRED_TARGETS = {"CAD", "LAD", "LCX", "RCA"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models and artifacts on startup"""
    logger.info("Initializing CardioLens API artifacts...")
    load_artifacts()
    yield
    logger.info("Shutting down CardioLens API")


# Create FastAPI app
app = FastAPI(
    title="CardioLens API",
    description="Interactive 3D Coronary Risk Visualization & Prediction API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CARDIOLENS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    models = get_all_models()
    manifest = get_manifest()
    schema = get_feature_schema()
    return {
        "status": "healthy" if REQUIRED_TARGETS.issubset(models) and schema is not None else "degraded",
        "model_version": manifest.get("version", "1.0.0"),
        "models_loaded": list(models.keys()),
        "schema_loaded": schema is not None
    }


@app.get("/schema", response_model=SchemaResponse)
async def get_schema():
    """Get feature schema for the frontend form"""
    schema = get_feature_schema()
    if schema is None:
        raise HTTPException(status_code=503, detail="Feature schema not loaded")
    return SchemaResponse(schema=schema)


@app.get("/samples", response_model=SamplesResponse)
async def get_samples():
    """Get preset sample patients for demonstration"""
    data_path = PROJECT_ROOT / "file.csv"
    if not data_path.exists():
        data_path = PROJECT_ROOT / "data" / "raw" / "z_alizadeh_sani_extension.csv"

    try:
        if data_path.exists():
            processor = CardioLensDataProcessor(str(PROJECT_ROOT / "ml" / "config.yaml"))
            df = processor.clean_data(pd.read_csv(data_path))

            samples = []
            # High risk patient sample
            cad_cases = df[df['Cath'].astype(str).str.lower() == 'cad'] if 'Cath' in df.columns else df
            if len(cad_cases) > 0:
                row = cad_cases.iloc[0].to_dict()
                clean_features = {k: v for k, v in row.items() if k not in ['Cath', 'CAD', 'LAD', 'LCX', 'RCA'] and pd.notna(v)}
                samples.append({
                    "name": "High Risk Patient (CAD+)",
                    "features": clean_features
                })

            # Low risk patient sample
            normal_cases = df[df['Cath'] == 'Normal'] if 'Cath' in df.columns else df
            if len(normal_cases) > 0:
                row = normal_cases.iloc[0].to_dict()
                clean_features = {k: v for k, v in row.items() if k not in ['Cath', 'CAD', 'LAD', 'LCX', 'RCA'] and pd.notna(v)}
                samples.append({
                    "name": "Low Risk Patient (Normal)",
                    "features": clean_features
                })

            # Mixed profile sample
            if len(df) > 5:
                row = df.iloc[5].to_dict()
                clean_features = {k: v for k, v in row.items() if k not in ['Cath', 'CAD', 'LAD', 'LCX', 'RCA'] and pd.notna(v)}
                samples.append({
                    "name": "Mixed Profile Patient",
                    "features": clean_features
                })

            return SamplesResponse(samples=samples)

    except Exception as e:
        logger.error(f"Error reading sample patient data: {e}")

    # Fallback preset samples
    default_samples = [
        {
            "name": "High Risk Patient",
            "features": {"Age": 68, "Sex": "Male", "BP": 150, "PR": 84, "DM": 1, "HTN": 1, "Typical Chest Pain": 1, "FBS": 160}
        },
        {
            "name": "Low Risk Patient",
            "features": {"Age": 42, "Sex": "Female", "BP": 115, "PR": 68, "DM": 0, "HTN": 0, "Typical Chest Pain": 0, "FBS": 85}
        },
        {
            "name": "Mixed Risk Patient",
            "features": {"Age": 55, "Sex": "Male", "BP": 135, "PR": 74, "DM": 0, "HTN": 1, "Typical Chest Pain": 0, "FBS": 110}
        }
    ]
    return SamplesResponse(samples=default_samples)


@app.post("/predict", response_model=PredictionResponse)
async def predict(feature_input: FeatureInput):
    """Get predictions and explanations for a patient"""
    models = get_all_models()
    if not REQUIRED_TARGETS.issubset(models):
        raise HTTPException(status_code=503, detail="Required models are unavailable")

    try:
        raw_dict = feature_input.features
        validate_input(raw_dict)
        # Preprocess features & fill schema defaults for any missing features
        input_df = preprocess_input(raw_dict)

        predictions = {}
        explanations = {}

        for target, model in models.items():
            prob, label, threshold = predict_target(model, input_df)
            predictions[target] = {
                "probability": prob,
                "label": label,
                "threshold": threshold
            }
            # Generate real SHAP explanations
            explanations[target] = explain_prediction(model, input_df)

        measurements = get_measurements(raw_dict)
        manifest = get_manifest()

        return PredictionResponse(
            model_version=manifest.get("version", "1.0.0"),
            predictions=predictions,
            explanations=explanations,
            measurements=measurements,
            disclaimer="Decision support / educational use only. Not a substitute for formal diagnostic imaging."
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Prediction failed") from e


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get stored evaluation results and metrics"""
    manifest = get_manifest()
    all_metrics = get_all_metrics()
    return MetricsResponse(
        model_version=manifest.get("version", "1.0.0"),
        evaluation=all_metrics,
        feature_importance=get_feature_importance()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
