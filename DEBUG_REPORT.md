# CardioLens debugging report

Reviewed `ps.pdf`, `architecture.md`, `pr.md`, and `tech-stack.md` before tracing the Python, API, and web code. The user-supplied `file.csv` supplies the vessel labels absent from `data.csv`.

## Confirmed and fixed

| Area | Root cause | Resolution |
|---|---|---|
| Data | The Y/N mapping included numeric lab fields and zeroed FBS, CR, LDL, and others. | Encode only categorical fields; preserve numeric values; regenerate artifacts. |
| Labels and leakage | `Cath='CAD'` was treated as negative; `CAD` could enter features. | Validate label vocabularies and exclude all target columns. |
| Modeling | Only CAD was configured; the trainer selected models using training-set metrics. | Train CAD/LAD/LCX/RCA from `file.csv`, select on training folds, report one untouched 20% test split, and save calibrated models. |
| Explanations | SHAP's two-class tree output was handled as a one-dimensional vector; zero-valued placeholders hid errors. | Select the positive-class SHAP slice; use transformed background; return no fabricated contributions on failure. |
| API | Unknown and target-named fields were silently ignored; prediction errors became zero risk; incomplete model loading still reported healthy. | Return validation/service errors and mark incomplete health as degraded. Restrict CORS origins. |
| Dashboard | Only eight hardcoded fields were editable, and the browser assumed `localhost:8000`. | Generate all 55 inputs from `/schema`; use `/api` proxy in development and Docker. |
| Measurements | Undefined ranges were displayed as `0–100 normal`; WBC and creatinine units were inconsistent with raw data. | Show only supported reference ranges and correct those units. Join SHAP contributions in the table. |
| Viewer colors | Selecting a vessel replaced its risk color with blue; probability colors jumped between three steps. | Keep a continuous green–yellow–red scale and enlarge the selected vessel. |
| Reproducibility | No startup manifest for dependencies or one-command run. | Add pinned Python requirements, local targets, Docker Compose, and usage documentation. |

## Verified

- `make test`: 18 Python tests, 3 web tests, TypeScript check, and production web build pass.
- `docker compose up --build -d`: API and web containers started; API health was healthy with four models.
- `http://localhost:8080/api/predict`: a preset returned four probabilities and four nonempty explanations in about 307 ms from the containerized app.
- Production npm audit (`--omit=dev`) found no known vulnerabilities at the time checked.

## Remaining gaps

- The 3D viewer uses procedural placeholder shapes. It lacks a licensed anatomical mesh, camera focus animation, and layer controls. There is no imaging-derived lesion localization.
- Candidate tuning is followed by repeated training-fold CV and a held-out test. The training-fold score is **not** a nested-CV estimate. The small test set makes vessel metrics uncertain; no confidence intervals or calibration curves are shown.
- The formal six-page submission document and demonstration video are not in the repository.
- The legacy Vite/Vitest development toolchain still has npm audit advisories. Production dependencies returned zero advisories, but the development toolchain needs a tested major-version upgrade.
- Python test output contains deprecation warnings from Pydantic, scikit-learn, Starlette, and SHAP. These do not currently fail tests but should be cleaned up before a long-lived deployment.
