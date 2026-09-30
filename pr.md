# PR — Project Requirements
## CardioLens: Interactive 3D Coronary Risk Visualization & Prediction
**Multimodal AI Hackathon 2026 · Track A**

---

## 1. Overview

CardioLens predicts overall Coronary Artery Disease (CAD) status and stenosis status of the three major coronary vessels (LAD, LCX, RCA) from tabular clinical data, then maps those predictions onto an interactive 3D heart/torso model. A clinical dashboard explains *why* each prediction was made using SHAP.

**One-line pitch:** turn four opaque probabilities into a rotatable, color-coded heart that a clinician can click to see exactly which measurements drove the risk.

## 2. Problem Statement

Statistical models return risk percentages, but numbers alone do not convey *where* pathology is developing or *why* the model believes it. We need a system that (a) predicts accurately and honestly on a small dataset, (b) spatially maps vessel-level risk, and (c) explains each prediction in physiological terms.

## 3. Goals and Non-Goals

### Goals
- G1. Train validated classifiers for **CAD, LAD, LCX, RCA** with leakage-free features.
- G2. Render an interactive 3D heart/torso with LAD/LCX/RCA colored by predicted probability.
- G3. Provide per-prediction explanations (SHAP) and a physiological breakdown.
- G4. Run smoothly in a modern browser **without a dedicated GPU**.
- G5. Keep the architecture extensible (new features, models, anatomical structures).

### Non-Goals
- Not a diagnostic device; no claim of clinical validity.
- No pixel-level or 3D lesion localization. `Region with RWMA` is used only as a tabular feature, never as a spatial coordinate.
- No image/DICOM ingestion (dataset is tabular).
- No user accounts, persistence of patient data, or real PHI handling.

## 4. Users and Use Cases

| User | Need | Use case |
|---|---|---|
| Clinician (demo persona) | Quickly see where risk concentrates and why | Enter patient values, inspect vessel risk, read SHAP drivers |
| Student / patient (educational) | Intuitive understanding of CAD | Rotate heart, click a vessel, read plain-language explanation |
| Hackathon judge | Verify rigor and integration | Review metrics, try sample patients, inspect code and docs |

## 5. Dataset

- **Source:** Extension of Z-Alizadeh Sani (UCI / Kaggle), 303 patients.
- **Inputs:** demographics, vitals, clinical exam, lab, ECG, echo (e.g. Age, BP, PR, cholesterol, enzymes, ST Elevation, T Inversion, LVH, Region with RWMA).
- **Targets:** `Cath` (overall CAD, ≥50% stenosis in a major vessel per dataset definition), `LAD`, `LCX`, `RCA`.
- **Leakage rule:** `LAD`, `LCX`, `RCA`, `Cath` are **always excluded** from input features.

## 6. Functional Requirements

### 6.1 Predictive Modeling (30%)
| ID | Requirement | Priority |
|---|---|---|
| ML-1 | Preprocess data: encode categoricals, binarize Y/N fields, handle missing/odd values, scale where needed, all inside a fitted `Pipeline` | Must |
| ML-2 | Train one binary classifier per target (CAD, LAD, LCX, RCA) | Must |
| ML-3 | Compare at least: Logistic Regression (baseline), Random Forest, XGBoost/LightGBM; choose best per target | Must |
| ML-4 | Validation: stratified k-fold (repeated), nested CV for hyperparameter tuning, plus a held-out test split; report mean ± std | Must |
| ML-5 | Report accuracy, precision, recall, F1, ROC-AUC (and PR-AUC for imbalanced vessels) per target | Must |
| ML-6 | Address class imbalance (class weights / threshold tuning) | Must |
| ML-7 | Probability calibration (Platt/isotonic) with calibration curve and Brier score | Should |
| ML-8 | Automated leakage test that fails if a target column appears in the feature list | Must |
| ML-9 | Save model artifacts (`.joblib`), feature schema, and metrics JSON with versioning | Must |

### 6.2 3D Visual Mapping (25%)
| ID | Requirement | Priority |
|---|---|---|
| VIZ-1 | Render interactive 3D torso and/or heart from open-source `.glb/.gltf` (BodyParts3D, Sketchfab, NIH 3D) | Must |
| VIZ-2 | Distinct, selectable nodes/meshes for **LAD, LCX, RCA** | Must |
| VIZ-3 | Color each vessel by predicted stenosis probability via a continuous green→yellow→red scale with legend | Must |
| VIZ-4 | Animate color transitions when a new prediction arrives | Should |
| VIZ-5 | Orbit, zoom, pan; click a vessel to focus camera and open its detail panel; hover tooltip | Must |
| VIZ-6 | Toggle layers: torso, heart, vessels; reset-view button | Should |
| VIZ-7 | Maintain ≥30 FPS on integrated graphics (decimated meshes, no heavy post-processing) | Must |
| VIZ-8 | Vessel-to-output mapping defined in one config file so labels, meshes, and predictions stay consistent | Must |

### 6.3 Clinical Dashboard (20%)
| ID | Requirement | Priority |
|---|---|---|
| DASH-1 | Patient input form generated from the feature schema (validated ranges, units, defaults) | Must |
| DASH-2 | Preset sample patients (high risk, low risk, mixed) for quick demo | Must |
| DASH-3 | Show overall CAD prediction + probability and LAD/LCX/RCA probabilities next to the 3D canvas | Must |
| DASH-4 | SHAP explanation per target: waterfall / top-N bar chart with direction (raises vs lowers risk) | Must |
| DASH-5 | Physiological measurement table showing value, reference range, and contribution to prediction | Must |
| DASH-6 | Global feature importance view (mean \|SHAP\|) and model metrics page | Should |
| DASH-7 | Plain-language summary sentence per vessel | Could |
| DASH-8 | Persistent, clearly visible **clinical safety disclaimer**: decision support / educational only, not a substitute for formal diagnostic imaging | Must |

### 6.4 System Integration (15%)
| ID | Requirement | Priority |
|---|---|---|
| SYS-1 | REST API serving predictions + explanations in a single call | Must |
| SYS-2 | Frontend updates 3D colors and dashboard in one round trip (<1 s typical) | Must |
| SYS-3 | Feature schema endpoint so the UI and API never drift apart | Must |
| SYS-4 | One-command local run (Docker Compose) | Must |

### 6.5 Technical Implementation (10%)
| ID | Requirement | Priority |
|---|---|---|
| TECH-1 | Modular, typed, linted code with tests for pipeline, API, and schema | Must |
| TECH-2 | Reproducible training (fixed seeds, pinned dependencies, single `make train`) | Must |
| TECH-3 | Extensibility: adding a feature, model, or vessel requires config changes, not rewrites | Must |
| TECH-4 | Document data and mesh licenses/attribution | Must |

## 7. Non-Functional Requirements

- **Performance:** API inference <200 ms; SHAP <500 ms (TreeExplainer, precomputed background).
- **Compatibility:** latest Chrome, Firefox, Edge, Safari; WebGL 2 with graceful fallback message.
- **Accessibility:** color scale also encoded by text labels/percentages (not color alone).
- **Privacy:** no patient data stored or logged; stateless API.
- **Safety:** disclaimer visible on every screen; probabilities framed as model estimates with uncertainty.

## 8. Success Metrics

| Area | Target (realistic for n=303) |
|---|---|
| CAD ROC-AUC | ≥ 0.90 (CV mean) |
| LAD ROC-AUC | ≥ 0.85 |
| LCX / RCA ROC-AUC | ≥ 0.75 (harder, imbalanced) |
| Calibration | Brier score reported; curve near diagonal |
| 3D performance | ≥30 FPS on integrated GPU |
| Explanation | Top-5 SHAP drivers shown for every target |
| Integration | Form submit → updated 3D + dashboard in <1 s |

Targets are aspirations; report whatever the honest CV numbers are.

## 9. Deliverables

| Deliverable | Contents | Owner |
|---|---|---|
| Working prototype | Web app with 3D viewer + ML backend | Full team |
| Prediction pipeline | Code, model weights, schema, metrics | ML |
| Explanation dashboard | Metrics, SHAP, physiological breakdown | Frontend + ML |
| Documentation (≤6 pages) | Preprocessing, models, 3D pipeline, usage, results | All |
| Demo video (3–10 min, YouTube) | Input workflow, 3D interaction, technical walkthrough | All |

### Documentation outline (6 pages)
1. Problem & dataset (0.5) · 2. Preprocessing & leakage control (1) · 3. Model architecture & validation (1.5) · 4. 3D pipeline (1) · 5. Explainability & dashboard (0.5) · 6. Results & limitations (1) · 7. Setup/usage (0.5)

### Demo video outline
0:00 problem → 0:45 enter patient → 1:30 3D rotate/zoom/click vessels → 3:00 SHAP breakdown → 4:30 architecture & ML validation → 6:30 limitations/disclaimer → wrap up.

## 10. Milestones

| Phase | Work | Output |
|---|---|---|
| 1. Data & baseline | EDA, cleaning, leakage guard, baseline models | Notebook + first metrics |
| 2. Model finalization | Tuning, nested CV, calibration, SHAP | Saved artifacts + metrics JSON |
| 3. API | FastAPI endpoints, schema, tests | Running backend |
| 4. 3D viewer | Load/optimize meshes, vessel nodes, color mapping | Interactive viewer |
| 5. Dashboard & integration | Form, results, SHAP charts, disclaimer | End-to-end app |
| 6. Polish & submit | Perf pass, docs, video, README | Final submission |

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Small dataset (303) → overfitting, unstable metrics | High | Repeated stratified/nested CV, simple models, report variance |
| Class imbalance on LCX/RCA | Med | Class weights, PR-AUC, threshold tuning |
| Target leakage | High | Explicit exclusion list + automated test |
| Open meshes lack coronary arteries | High | Build LAD/LCX/RCA procedurally as tube geometries over a heart mesh; keep in config |
| Heavy meshes hurt FPS | Med | Decimate, compress (Draco/Meshopt), lazy load |
| Over-interpreting SHAP or RWMA as spatial | Med | Explicit limitation notes; RWMA treated as a feature only |
| Misread as medical advice | High | Persistent disclaimer, careful wording |
| Uncalibrated probabilities mislead color scale | Med | Calibration step and reliability plot |

## 12. Open Questions

- Which mesh source gives the best license + quality (BodyParts3D vs Sketchfab CC-BY)?
- Include a torso context layer, or heart only, for performance?
- Client-side (ONNX) inference as a backend-free fallback?

## 13. Acceptance Checklist

- [ ] Target columns excluded from features (test passes)
- [ ] Metrics table for CAD, LAD, LCX, RCA (acc, prec, rec, F1, ROC-AUC)
- [ ] 3D heart rotates, zooms, selects LAD/LCX/RCA
- [ ] Vessel colors update from live predictions
- [ ] SHAP chart + measurement contribution table shown
- [ ] Disclaimer visible on all views
- [ ] `docker compose up` runs the full app
- [ ] Docs ≤6 pages, video 3–10 min on YouTube
