# Architecture — CardioLens
**Multimodal AI Hackathon 2026 · Track A**

---

## 1. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **ML / data** | Python 3.11, pandas, NumPy, scikit-learn, XGBoost / LightGBM | Strong on small tabular data; `Pipeline` prevents preprocessing leakage |
| **Explainability** | SHAP (`TreeExplainer` / `LinearExplainer`) | Fast, exact for tree models; per-prediction attributions |
| **Model tuning** | Optuna or sklearn `GridSearchCV` inside nested CV | Honest estimates on n=303 |
| **Persistence** | joblib + JSON (schema, metrics, background sample) | Simple, versionable |
| **Backend API** | FastAPI + Pydantic + Uvicorn | Typed request/response validation, auto OpenAPI docs |
| **Frontend** | React 18 + TypeScript + Vite | Fast dev loop, typed components |
| **3D rendering** | Three.js via React Three Fiber + `@react-three/drei` | Declarative scene, OrbitControls, picking, GLTF loading |
| **State** | Zustand | Lightweight shared state for prediction + selected vessel |
| **Charts** | Recharts (or D3) | SHAP bars/waterfall, metrics, calibration |
| **Styling / UI** | Tailwind CSS + shadcn/ui | Quick, consistent dashboard |
| **Forms** | React Hook Form + Zod (schema-driven) | Validation generated from feature schema |
| **3D assets** | BodyParts3D / Sketchfab / NIH 3D `.glb` | Open-source anatomy; optimized with `gltf-transform` (Draco/Meshopt), Blender for cleanup |
| **Testing** | pytest, Vitest, Playwright (smoke) | Pipeline, API, UI, end-to-end |
| **Tooling** | Ruff, Black, mypy, ESLint, Prettier, Makefile | Code quality |
| **Deploy / repro** | Docker + Docker Compose, pinned `requirements.txt` / lockfile | One-command run |
| **Hosting (optional)** | Render / Fly.io / HF Spaces (API), Vercel / Netlify (UI) | Public demo link |

## 2. System Overview

```
┌──────────────────────────────── Browser ────────────────────────────────┐
│                                                                         │
│  ┌────────────────┐   ┌──────────────────────┐   ┌───────────────────┐  │
│  │ Patient Form   │   │  3D Viewer (R3F)     │   │ Clinical Dashboard│  │
│  │ (schema-driven)│   │  heart + LAD/LCX/RCA │   │ probs, SHAP,      │  │
│  └───────┬────────┘   └──────────▲───────────┘   │ measurements      │  │
│          │                       │ colors        └─────────▲─────────┘  │
│          ▼                       │                         │            │
│   ┌──────────────────────── Zustand store ─────────────────┴─────────┐  │
│   │ patient · prediction · explanation · selectedVessel · schema      │  │
│   └──────────────────────────────┬────────────────────────────────────┘  │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │ HTTPS / JSON
                          ┌────────▼─────────┐
                          │   FastAPI         │
                          │ /schema /predict  │
                          │ /metrics /samples │
                          └────────┬─────────┘
                                   │
               ┌───────────────────┼─────────────────────┐
               ▼                   ▼                     ▼
       ┌───────────────┐  ┌────────────────┐   ┌──────────────────┐
       │ Preprocessing │  │ Model registry │   │ SHAP explainers  │
       │ (fitted       │→ │ CAD·LAD·LCX·RCA│ → │ per target       │
       │  Pipeline)    │  │ (calibrated)   │   │ + background set │
       └───────────────┘  └────────────────┘   └──────────────────┘
               ▲
               │ produced offline by training pipeline
       ┌───────┴──────────────────────────────────────────────┐
       │ data/raw → clean → features → CV/tune → calibrate →  │
       │ evaluate → artifacts/ (joblib, schema.json, metrics) │
       └──────────────────────────────────────────────────────┘
```

**Principle:** training is offline and produces immutable artifacts; the API is stateless and only loads artifacts; the UI is driven by the API's schema and a single vessel config.

## 3. Repository Structure

```
cardiolens/
├── README.md
├── pr.md
├── architecture.md
├── docker-compose.yml
├── Makefile                      # make train | api | web | test | all
├── data/
│   ├── raw/                      # Z-Alizadeh Sani (not committed if license requires)
│   └── processed/
├── ml/
│   ├── config.yaml               # targets, excluded cols, seeds, model grid
│   ├── src/cardiolens_ml/
│   │   ├── data.py               # load, clean, type coercion
│   │   ├── features.py           # feature schema, encoders, leakage guard
│   │   ├── pipeline.py           # sklearn Pipeline builders
│   │   ├── train.py              # nested CV, tuning, final fit
│   │   ├── calibrate.py
│   │   ├── evaluate.py           # metrics, curves, tables
│   │   ├── explain.py            # SHAP explainers + background
│   │   └── registry.py           # save/load artifacts
│   ├── notebooks/                # EDA, experiments
│   └── tests/                    # leakage, schema, determinism
├── artifacts/                    # generated: models/*.joblib, schema.json, metrics.json, shap_background.parquet
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/ (predict.py, schema.py, metrics.py, samples.py)
│   │   ├── schemas.py            # Pydantic models
│   │   ├── services/ (inference.py, explanation.py)
│   │   └── settings.py
│   ├── tests/
│   └── Dockerfile
└── web/
    ├── public/models/            # optimized .glb (torso, heart)
    ├── src/
    │   ├── config/vessels.ts     # single source of truth: vessel ↔ mesh ↔ target
    │   ├── api/client.ts
    │   ├── store/useCardioStore.ts
    │   ├── components/
    │   │   ├── viewer/ (Scene, HeartModel, VesselMesh, Legend, Controls)
    │   │   ├── dashboard/ (RiskSummary, ShapChart, MeasurementTable, MetricsPanel)
    │   │   ├── form/ (PatientForm, SamplePicker)
    │   │   └── common/ (DisclaimerBanner)
    │   ├── lib/colorScale.ts
    │   └── App.tsx
    ├── tests/
    └── Dockerfile
```

## 4. ML Pipeline

### 4.1 Data preparation
1. Load Z-Alizadeh Sani (303 rows).
2. Normalize column names; coerce types.
3. Map targets: `Cath` → `CAD` (binary), `LAD/LCX/RCA` → binary stenosis (0/1).
4. Encode: Y/N → 0/1; Sex → binary; categorical (e.g. BP categories, Region RWMA, VHD) → one-hot / ordinal as appropriate.
5. **Leakage guard:** `features.py` defines `EXCLUDED = {LAD, LCX, RCA, Cath}`; a test asserts no overlap with the feature list; the pipeline raises if a target appears.
6. Save the feature schema (name, type, unit, min/max, default, reference range, group) to `artifacts/schema.json`. The API and UI both consume it.

### 4.2 Modeling
- Four independent binary classifiers (CAD, LAD, LCX, RCA). Independent models keep explanations clean and vessel outputs decoupled.
- Candidates: Logistic Regression (scaled, L1/L2), Random Forest, XGBoost/LightGBM. Choose per target by CV ROC-AUC with PR-AUC as tiebreaker for imbalanced vessels.
- Imbalance: `class_weight` / `scale_pos_weight`; decision threshold tuned on out-of-fold predictions (F1 or Youden's J).
- All preprocessing lives inside the sklearn `Pipeline` so scaling/imputation are fit only on training folds.

### 4.3 Validation
- Outer: repeated stratified 5-fold CV (e.g. 5×5) for reported performance.
- Inner: stratified CV for hyperparameter search (nested).
- Additional held-out stratified test split (e.g. 20%) for a final sanity check.
- Metrics per target: accuracy, precision, recall, F1, ROC-AUC, PR-AUC, Brier; confusion matrix; ROC and calibration curves. Report mean ± std.

### 4.4 Calibration
Wrap the final estimator with `CalibratedClassifierCV` (sigmoid preferred at this sample size; isotonic only if it demonstrably helps). Colors on the 3D model are driven by calibrated probabilities.

### 4.5 Explainability
- `TreeExplainer` for tree models, `LinearExplainer` for logistic regression.
- Background set saved to artifacts for reproducible values.
- Per prediction: top-N SHAP contributions (signed) for each target, plus base value.
- Global: mean |SHAP| ranking computed offline and stored in `metrics.json`.
- If a calibrated wrapper obscures the base estimator, explain the underlying estimator and note that SHAP values are in the model's raw output space (log-odds for boosted trees/LR).

### 4.6 Artifacts
```
artifacts/
├── models/{cad,lad,lcx,rca}.joblib
├── schema.json
├── metrics.json            # CV results, thresholds, global importances
├── shap_background.parquet
└── manifest.json           # version, git hash, seed, training date, data checksum
```

## 5. API Design

Base: `/api/v1`

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Liveness + model version |
| GET | `/schema` | Feature schema (types, ranges, units, defaults, reference ranges) |
| GET | `/samples` | Preset patients (high/low/mixed risk) |
| GET | `/metrics` | Stored evaluation results and global importances |
| POST | `/predict` | Predictions + explanations for one patient |

### `POST /predict`
**Request**
```json
{ "features": { "Age": 58, "Sex": "Male", "HTN": 1, "BP": 140, "PR": 78, "...": "..." } }
```
**Response**
```json
{
  "model_version": "2026.1.0",
  "predictions": {
    "CAD": { "probability": 0.87, "label": 1, "threshold": 0.46 },
    "LAD": { "probability": 0.74, "label": 1, "threshold": 0.41 },
    "LCX": { "probability": 0.22, "label": 0, "threshold": 0.35 },
    "RCA": { "probability": 0.51, "label": 1, "threshold": 0.44 }
  },
  "explanations": {
    "LAD": {
      "base_value": -0.4,
      "contributions": [
        { "feature": "Typical Chest Pain", "value": 1, "shap": 0.63 },
        { "feature": "Age", "value": 58, "shap": 0.31 }
      ]
    }
  },
  "measurements": [
    { "feature": "BP", "value": 140, "unit": "mmHg", "ref_range": [90, 120], "status": "high" }
  ],
  "disclaimer": "Decision support / educational use only. Not a substitute for formal diagnostic imaging."
}
```

**Design notes**
- Pydantic validates ranges from `schema.json`; unknown or target-named fields return `422`.
- Models and explainers load once at startup (lifespan handler).
- Stateless, no request body logging (privacy).
- CORS restricted to the frontend origin.

## 6. Frontend and 3D Architecture

### 6.1 Scene
- `Canvas` (R3F) with `OrbitControls` (rotate/zoom/pan, clamped distance), soft ambient + directional lighting, no expensive post-processing.
- Layers: **torso** (translucent, toggleable) → **heart** (opaque/semi-opaque) → **coronary vessels** (highlighted).
- Loader: `useGLTF` with Draco/Meshopt decoding; assets lazy-loaded with a `Suspense` fallback.

### 6.2 Coronary vessel strategy
Most open heart meshes do not include separate coronary arteries. Plan:
1. Use a heart `.glb` as anatomical context.
2. Define LAD, LCX, RCA as **`TubeGeometry` along `CatmullRomCurve3` paths** whose control points are placed on the heart surface (authored once, stored in `vessels.ts` or a JSON file). Each vessel is a separate mesh with its own material.
3. If a mesh already has named vessel nodes, map them by name instead.

Because vessels are separate meshes, per-vessel color, raycast picking, hover, and camera focus are trivial.

### 6.3 Single source of truth: `vessels.ts`
```ts
export const VESSELS = [
  { id: "LAD", label: "Left Anterior Descending", target: "LAD", meshName: "vessel_LAD", focus: [x,y,z], region: "Front of heart" },
  { id: "LCX", label: "Left Circumflex",          target: "LCX", meshName: "vessel_LCX", focus: [x,y,z], region: "Side and back" },
  { id: "RCA", label: "Right Coronary Artery",    target: "RCA", meshName: "vessel_RCA", focus: [x,y,z], region: "Right side and bottom" },
] as const;
```
This file binds **mesh ↔ model target ↔ UI label ↔ camera focus**, satisfying the requirement for consistent output-to-anatomy correspondence. Adding a structure means adding one entry (plus a trained target).

### 6.4 Risk-to-color mapping
- `colorScale.ts`: continuous scale green (0) → yellow (0.5) → red (1) via interpolated `THREE.Color`; the same function colors the legend and the dashboard badges.
- Colors animate via `useFrame` lerp toward target color (smooth transitions).
- Not color alone: each vessel also shows a percentage label and a risk band text (Low / Moderate / High).

### 6.5 Interaction
- Click vessel → store `selectedVessel` → camera eases to `focus`, detail panel opens (probability, SHAP for that target, region description).
- Hover → highlight + tooltip; click empty space → deselect.
- Reset-view and layer-toggle controls.

### 6.6 Performance budget (no dedicated GPU)
- Heart ≤ ~100k triangles, torso decimated (≤ ~150k) and Draco-compressed; total download target < 8 MB.
- Limit pixel ratio (`dpr={[1, 1.5]}`), no shadows/SSAO, `frameloop="demand"` with invalidation on interaction/animation.
- Reuse materials/geometries; dispose on unmount.

### 6.7 Dashboard components
| Component | Content |
|---|---|
| `RiskSummary` | Overall CAD status + 3 vessel probabilities, risk bands |
| `ShapChart` | Signed top-N contributions per selected target (toggle CAD/LAD/LCX/RCA) |
| `MeasurementTable` | Feature, value, reference range, status flag, SHAP contribution bar |
| `MetricsPanel` | CV metrics, ROC/calibration curves, global importances |
| `DisclaimerBanner` | Sticky, always visible |
| `PatientForm` | Grouped inputs (demographics, exam, lab, ECG, echo) generated from `/schema` |

### 6.8 Data flow
1. App boot → `GET /schema` (build form) and `GET /samples`.
2. User edits form or picks sample → `POST /predict` (debounced/submit).
3. Store updates `prediction`, `explanation`, `measurements`.
4. 3D vessel materials, risk summary, SHAP chart, and table re-render from the same store slice, so they cannot disagree.

## 7. Extensibility

| Change | What to touch |
|---|---|
| Add clinical feature | Add to dataset processing + rerun `make train`; schema regenerates; form and table pick it up automatically |
| Add/replace model | Register in `ml/config.yaml` model grid; artifact loads by name |
| Add anatomical structure/target | Add target to `config.yaml`, add mesh/curve + `vessels.ts` entry |
| Swap 3D asset | Replace `.glb`, adjust vessel curves/focus points |

## 8. Testing Strategy

| Level | Tests |
|---|---|
| ML | Leakage guard, schema consistency, deterministic training with fixed seed, metric sanity bounds |
| API | Contract tests for `/predict`, validation errors, rejects target columns, response schema |
| Frontend | Unit tests for `colorScale`, store, `vessels.ts` integrity; component tests for form and charts |
| E2E | Playwright: load app → pick sample → vessel colors change → click vessel opens detail → disclaimer visible |
| Performance | Manual FPS check on integrated GPU; bundle and asset size budget |

## 9. Deployment and Reproducibility

- `docker-compose.yml`: `api` (FastAPI, artifacts mounted/baked) and `web` (Vite build served by Nginx).
- `make train` regenerates artifacts from `data/raw` with fixed seeds; `manifest.json` records versions and data checksum.
- Pinned dependencies (`requirements.txt` / `uv.lock`, `package-lock.json`).
- Run instructions in README: `make all` or `docker compose up`.

## 10. Safety, Ethics, and Limitations

- Persistent disclaimer: predictions are for **decision support / educational purposes only** and not a substitute for formal diagnostic imaging.
- The 3D model shows **model-predicted risk per named vessel**, not an imaging-derived lesion location; `Region with RWMA` is a tabular input only.
- Small single-source dataset (n=303) limits generalizability; report CV variance and avoid overclaiming.
- SHAP shows model associations, not causal effects.
- Attribute all datasets and 3D assets with their licenses in the README.

## 11. Decision Log

| Decision | Alternative | Rationale |
|---|---|---|
| Independent per-target classifiers | Multi-output / classifier chain | Simpler, cleaner per-vessel SHAP; chain can be an ablation |
| Gradient boosting + LR baseline | Deep learning | 303 tabular rows; trees/linear are stronger and explainable |
| Server-side inference (FastAPI) | Client-side ONNX | Easier SHAP and model management; ONNX is a fallback option |
| Procedural vessel tubes | Find mesh with coronaries | Guaranteed separate, selectable, colorable nodes |
| React Three Fiber | Raw Three.js / VTK.js | Declarative state-driven updates, ecosystem (drei) |
| Zustand | Redux | Minimal boilerplate for a small shared state |
