# Coronary Atlas frontend

Next.js 16, React, TypeScript and Three.js connect to a local FastAPI inference
service. Existing models are loaded without retraining or changing their weights.

## One-command Docker start

From the repository root:

```bash
docker compose up --build
```

Open http://localhost:3000. Stop with Ctrl+C and `docker compose down`.
To use a different host port: `PORT=3001 docker compose up --build`.
Only the frontend is published, on loopback. The API stays within the Compose
network. This is a local research prototype; public clinical hosting is outside
the scope of this implementation.

## Local development

```bash
.venv/bin/pip install -r requirements-api.txt
.venv/bin/python -m uvicorn cardio_nb.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

The Next.js API proxy defaults to http://127.0.0.1:8000. Set MODEL_API_URL to
change it. Browser requests use the same origin; there is no browser CORS setup.

## Prediction policy

| Target | Artifact | Mean outer-fold ROC-AUC |
|---|---|---:|
| CAD | artifacts/Cath.joblib | 0.9208 |
| LAD | artifacts/LAD.joblib | 0.8427 |
| LCX | artifacts/fixed/LCX.joblib | 0.7167 |
| RCA | artifacts/RCA.joblib | 0.7222 |

These choices follow the strongest observed AUC for each target. The mixed
selection itself has not been externally validated; reported AUC is per-model
cross-validation, not a new evaluation of this combined deployment strategy.
The original command-line predictor still defaults to the all-tuned folder;
the web API explicitly applies the per-target policy above.

All 55 non-target columns have a form field, in six sections, with search.
Exactly those 55 keys must be submitted. Invalid categories and numeric values
are rejected; missing values are explicitly allowed and reported. Measurements
outside the observed training range produce a warning, not a medical diagnosis.
Unspecified laboratory units are labeled dataset units; use the source data scale.

The initial form is a synthetic reference assembled from medians/modes, labeled
as such. Predictions are never fabricated before submission. Editing inputs
marks previous scores as stale and removes risk colors until reassessment.
No patient history is stored or logged by the app; exporting a JSON assessment
is an explicit user action.

Feature selection remains intact. CAD uses 35 features, LAD 20, RCA 10, and
fixed LCX 54. Thus every nonconstant feature can affect at least one selected
model, but not every target. Exertional CP was constant and has zero learned
influence. Feature explanations are exact additive NB log-likelihood ratios
before probability calibration, not causal attributions. The all-input view
explicitly marks unselected fields. LCX probability is uncalibrated.

## Anatomy

72 original BodyParts3D OBJ meshes are served locally, with no runtime dependency
on the source server. Original alignment is preserved using a single transform.
LAD, LCX and RCA are selectable and colored continuously by model probability.
The heart can be rotated, zoomed, reset, expanded, and made transparent.
If WebGL or the assets are unavailable, the viewer reports a failure while the
prediction panels remain usable. See [anatomy sources](anatomy-sources.md) for
identifiers, exact source URLs, hashes, attribution, and license details.

The rendered heart is a reference atlas. Artery colors do not locate a lesion
and do not represent percentage narrowing. The interface visibly states that
this is for research/education, not a substitute for diagnostic imaging.

## Checks

```bash
.venv/bin/python -m pytest -q
cd frontend
npm run build
```
