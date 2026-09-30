# CardioLens

CardioLens is a web prototype for estimating overall coronary artery disease (CAD) and LAD, LCX, and RCA stenosis from clinical data. It shows four model probabilities, per-target SHAP explanations, and a rotatable risk visualization. **Educational decision support only:** it does not locate lesions or replace diagnostic imaging.

## Run with Docker (recommended)

**You need:** Docker Desktop, or Docker Engine with the Compose plugin. Python, Node.js, and the machine-learning packages are installed *inside* the containers. The first build needs an internet connection to download base images and dependencies; later starts reuse the built images.

1. Download and extract this repository, or the `cardiolens-docker-bundle.zip` archive. Keep `file.csv` and the four model files in `ml/artifacts/models/` alongside the source files.
2. Open a terminal in the extracted folder (the folder containing `docker-compose.yml`).
3. Run:

   ```bash
   docker compose up --build -d
   ```

4. Open [http://localhost:8080](http://localhost:8080). The API documentation is at [http://localhost:8080/api/docs](http://localhost:8080/api/docs).

The web container serves the React app and forwards `/api` requests to the Python container. Compose waits for all four models and the schema to load before starting the web service. No separate API port or environment file is required.

### Useful Docker commands

```bash
docker compose ps                 # See service health and port
docker compose logs -f api        # Inspect API startup and errors (Ctrl+C to exit logs)
docker compose down               # Stop and remove the app containers
docker compose up -d              # Start again using the built images
docker compose up --build -d      # Rebuild after changing code or artifacts
```

If port 8080 is already used, run `CARDIOLENS_PORT=8081 docker compose up --build -d` and open `http://localhost:8081`. In PowerShell, set `$env:CARDIOLENS_PORT=8081` before running `docker compose up --build -d`.

If the web service does not start, run `docker compose ps` and `docker compose logs api`. A missing `file.csv` or model artifact is a common cause; confirm that `ml/artifacts/models/CAD.joblib`, `LAD.joblib`, `LCX.joblib`, and `RCA.joblib` are present. Docker health is reported as healthy only when all four models and the feature schema load.

To create a fresh shareable source archive from this workspace, run `python3 scripts/package_bundle.py`. The archive includes the dataset and trained artifacts; check the dataset's redistribution terms before publishing it.

## Local development without Docker

Install Python 3.11 and Node.js 20 or newer, then run from the project root:

```bash
make setup
make api
```

In a second terminal, run `make web` and open [http://localhost:5173](http://localhost:5173). The Vite development server proxies `/api` to the local FastAPI server. `make test` runs Python tests, web tests, TypeScript checking, and a production web build.

`make train` retrains all four models from `file.csv` and rewrites `ml/artifacts/`. Run it before rebuilding Docker if you change the dataset or training code. Training is optional for running the provided prototype because the bundle already includes model weights.

## Data and model

`file.csv` contains 303 patients, 55 clinical inputs, vessel labels (`Stenotic`/`Normal`), and an overall `Cath` label (`CAD`/`Normal`). `CAD`, `Cath`, `LAD`, `LCX`, and `RCA` are excluded from model inputs. Numeric labs are preserved, and categorical clinical fields are encoded. The API provides a feature schema used by the input form.

For each target, training reserves a stratified 20% test split. Candidate models are tuned and compared on training folds; the selected calibrated model is then evaluated once on the held-out split and refit on all 303 patients for deployment. Training-fold scores are **not** nested-CV estimates. The test split contains only 61 patients, so metrics have substantial uncertainty.

| Target | Held-out ROC-AUC | F1 | Brier score |
|---|---:|---:|---:|
| CAD | 0.855 | 0.882 | 0.138 |
| LAD | 0.834 | 0.842 | 0.155 |
| LCX | 0.716 | 0.524 | 0.209 |
| RCA | 0.738 | 0.487 | 0.198 |

The full results are in `ml/artifacts/evaluation_report.txt`. `ml/artifacts/manifest.json` records the input checksum and feature count. Python package versions are pinned in `requirements.txt`; the web build uses `web/package-lock.json` with `npm ci`.

## Interpretation and current limits

The viewer uses lightweight **placeholder heart and vessel shapes**. Vessel color follows a continuous green → yellow → red scale for model-estimated stenosis probability. It is not an imaging-derived lesion map. SHAP contributions describe associations in the base estimator's output; the displayed calibrated probability can use a different scale. SHAP values are not causal explanations.

A licensed anatomical `.glb` mesh, camera focus animation, layer controls, calibration curves, uncertainty intervals, a formal six-page submission document, and a demonstration video are not yet included. See `DEBUG_REPORT.md` for the debugging record and remaining requirements.

The supplied `file.csv` is an extension of the Z-Alizadeh Sani dataset described in `ps.pdf`. Verify and record its redistribution terms before publishing the dataset. The current viewer contains no third-party mesh asset.
