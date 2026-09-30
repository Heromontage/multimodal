# Tech Stack — CardioLens
**Multimodal AI Hackathon 2026 · Track A**

---

## At a Glance

| Layer | Technology |
|---|---|
| Language (ML/API) | Python 3.11 |
| Data | pandas, NumPy |
| Modeling | scikit-learn, XGBoost, LightGBM |
| Tuning | Optuna (or `GridSearchCV`) with nested CV |
| Explainability | SHAP (`TreeExplainer` / `LinearExplainer`) |
| Persistence | joblib, JSON, Parquet |
| Backend | FastAPI, Pydantic v2, Uvicorn |
| Frontend | React 18, TypeScript, Vite |
| 3D | Three.js via React Three Fiber, `@react-three/drei` |
| State | Zustand |
| Charts | Recharts (D3 for custom SHAP waterfall if needed) |
| UI | Tailwind CSS, shadcn/ui |
| Forms | React Hook Form, Zod |
| 3D assets | BodyParts3D / Sketchfab / NIH 3D (`.glb`), `gltf-transform`, Blender |
| Testing | pytest, Vitest, Playwright |
| Quality | Ruff, Black, mypy, ESLint, Prettier |
| DevOps | Docker, Docker Compose, Makefile, GitHub Actions |
| Hosting (optional) | Render / Fly.io / HF Spaces (API), Vercel / Netlify (UI) |

---

## 1. Machine Learning

| Tool | Role | Why |
|---|---|---|
| **Python 3.11** | Core language | Best ecosystem for tabular ML |
| **pandas / NumPy** | Loading, cleaning, encoding | Standard for a 303-row dataset |
| **scikit-learn** | `Pipeline`, `ColumnTransformer`, CV, metrics, calibration | Keeps preprocessing inside folds, preventing leakage |
| **XGBoost / LightGBM** | Gradient-boosted candidates | Strong on small tabular data, native `scale_pos_weight` for imbalance |
| **Logistic Regression** | Interpretable baseline | Reference model, works well at n=303 |
| **Random Forest** | Second baseline | Robust, low tuning cost |
| **Optuna** | Hyperparameter search | Efficient, works inside inner CV loop |
| **CalibratedClassifierCV** | Probability calibration | Colors on the 3D model depend on trustworthy probabilities |
| **SHAP** | Per-prediction and global attributions | Fast, exact for tree models |
| **matplotlib / seaborn** | Offline plots (ROC, calibration, confusion matrix) | For the 6-page report |
| **joblib** | Model serialization | Simple, sklearn-native |
| **Jupyter** | EDA and experiments | Quick iteration |

**Validation:** repeated stratified 5-fold CV (outer), stratified CV (inner tuning), plus a held-out test split.
**Metrics:** accuracy, precision, recall, F1, ROC-AUC, PR-AUC, Brier score.

## 2. Backend

| Tool | Role | Why |
|---|---|---|
| **FastAPI** | REST API | Async, typed, auto OpenAPI docs |
| **Pydantic v2** | Request/response validation | Ranges generated from the feature schema |
| **Uvicorn** | ASGI server | Lightweight, production-capable |
| **python-dotenv / pydantic-settings** | Config | Environment-based settings |

**Endpoints:** `GET /health`, `GET /schema`, `GET /samples`, `GET /metrics`, `POST /predict`.
Models and SHAP explainers load once at startup; the API is stateless and stores no patient data.

## 3. Frontend

| Tool | Role | Why |
|---|---|---|
| **React 18 + TypeScript** | UI framework | Typed, component-based |
| **Vite** | Build tool | Fast dev server and builds |
| **Zustand** | Global state | Minimal boilerplate for patient, prediction, selected vessel |
| **React Hook Form + Zod** | Patient form | Schema-driven validation |
| **Tailwind CSS + shadcn/ui** | Styling and components | Fast, consistent dashboard |
| **Recharts** | SHAP bars, metrics, calibration curves | Simple declarative charts |
| **Axios / fetch** | API client | Typed wrapper in `api/client.ts` |

## 4. 3D Visualization

| Tool | Role | Why |
|---|---|---|
| **Three.js** | WebGL rendering | Mature, runs without a dedicated GPU |
| **React Three Fiber** | Declarative Three.js in React | Scene updates driven by app state |
| **@react-three/drei** | `OrbitControls`, `useGLTF`, `Html`, `Bounds` helpers | Rotate/zoom/pan, loading, tooltips, camera focus |
| **GLTFLoader + Draco/Meshopt** | Compressed model loading | Small downloads, fast load |
| **TubeGeometry + CatmullRomCurve3** | Procedural LAD/LCX/RCA vessels | Guarantees separate, selectable, colorable nodes |
| **THREE.Color lerp** | Risk color scale (green → yellow → red) | Smooth animated updates |
| **Raycasting (R3F events)** | Hover and click picking | Vessel selection and detail panel |

**Asset pipeline:** source `.glb/.obj` (BodyParts3D, Sketchfab CC-BY, NIH 3D) → clean/decimate in Blender → compress with `gltf-transform` → place in `web/public/models/`.
**Budget:** heart ≤ ~100k triangles, total assets < 8 MB, no shadows or post-processing, pixel ratio capped at 1.5.

## 5. Testing and Quality

| Area | Tools | Covers |
|---|---|---|
| ML | pytest | Leakage guard, schema consistency, deterministic training |
| API | pytest + httpx | `/predict` contract, validation errors, rejects target columns |
| Frontend | Vitest + Testing Library | `colorScale`, store, `vessels.ts`, form |
| E2E | Playwright | Pick sample → vessel colors change → click vessel → disclaimer visible |
| Style | Ruff, Black, mypy, ESLint, Prettier | Consistency and type safety |
| CI | GitHub Actions | Lint + tests on push |

## 6. DevOps and Reproducibility

| Tool | Role |
|---|---|
| **Docker + Docker Compose** | One-command run (`api` + `web`) |
| **Makefile** | `make train`, `make api`, `make web`, `make test`, `make all` |
| **requirements.txt / uv.lock, package-lock.json** | Pinned dependencies |
| **manifest.json** | Records model version, git hash, seed, data checksum |
| **Fixed random seeds** | Reproducible training |

## 7. Data and Asset Sources

| Resource | Use | License note |
|---|---|---|
| Z-Alizadeh Sani extension (UCI / Kaggle) | 303-patient training data | Cite per UCI terms |
| BodyParts3D | Anatomy meshes | Check CC-BY-SA attribution |
| Sketchfab / NIH 3D Print Exchange | Heart model | Verify each model's license |

Record all attributions in the README.

## 8. Alternatives Considered

| Choice | Alternative | Why not |
|---|---|---|
| Boosted trees + LR | Deep learning | 303 tabular rows; harder to explain and tune |
| FastAPI server inference | Client-side ONNX | SHAP and model management are easier server-side (kept as fallback) |
| React Three Fiber | Raw Three.js / VTK.js | R3F fits state-driven updates; VTK.js is heavier |
| Zustand | Redux | Too much boilerplate for this scope |
| Recharts | D3 only | Slower to build; D3 only for custom waterfall |
| Independent per-target models | Multi-output / classifier chain | Cleaner per-vessel SHAP (chain is an ablation option) |

## 9. Minimal Install Reference

```bash
# ML + API
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy scikit-learn xgboost lightgbm optuna shap joblib \
            matplotlib seaborn fastapi "uvicorn[standard]" pydantic pydantic-settings \
            pytest httpx ruff black mypy

# Frontend
npm create vite@latest web -- --template react-ts
cd web
npm i three @react-three/fiber @react-three/drei zustand recharts \
      react-hook-form zod axios
npm i -D tailwindcss vitest @testing-library/react playwright eslint prettier
```
