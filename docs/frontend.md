# Coronary Atlas frontend

Next.js 16, React, TypeScript and Three.js connect to a local FastAPI inference
service. Existing models are loaded without retraining or changing their weights.

## Docker start

From the repository root:

```bash
python scripts/configure_database.py
docker compose up --build -d
```

Open http://localhost:3000 and choose **Sign up**. The configuration command
creates random database passwords in the ignored local .env file without
overwriting existing credentials. Keep that file for subsequent restarts.
Use PORT in .env to change the frontend host port.

MySQL 8.4, the prediction API, and the frontend run in Docker. Only the frontend
is published, on loopback. MySQL data lives in the mysql-data named volume and
survives container restarts. `docker compose down` keeps that volume;
`docker compose down -v` deletes all accounts and saved inputs.

## Accounts and saved inputs

Email/password signup and signin use Argon2 password hashes. Login sessions are
random tokens stored as hashes in MySQL and sent in HttpOnly, SameSite=Strict
cookies. Sessions expire after seven days and are revoked on signout.
Repeated failed signin attempts temporarily lock the account for 15 minutes.

Each account has one latest saved set of all 55 inputs, including missing values.
New accounts start with reference values. Signing in or refreshing restores the
saved values. Edits and Reset only change the browser form. The API validates all
55 submitted fields, calculates the four predictions, and then replaces the saved
inputs in one transaction. Invalid inputs, inference failures, and database
failures do not produce a successful assessment save. Predictions are calculated
on demand; the database stores the account, password hash, sessions, and inputs.

COOKIE_SECURE defaults to false for localhost HTTP. Set COOKIE_SECURE=true when
serving this app through HTTPS. The proxy rejects browser mutation requests from
other origins. MySQL credentials are never included in frontend code or exports.

## Local development

For a local frontend against the Docker API:

```bash
python scripts/configure_database.py
docker compose -f compose.yaml -f compose.dev.yaml up -d --build mysql model-api
cd frontend
npm ci
npm run dev -- --port 3001
```

The development override publishes the API on 127.0.0.1:8000 and MySQL on
127.0.0.1:3307. For a locally running Python API, install requirements-api.txt and
set DB_HOST=127.0.0.1, DB_PORT=3307, DB_NAME=coronary_atlas, DB_USER=coronary,
and DB_PASSWORD to MYSQL_PASSWORD from .env. DATABASE_URL is also supported.
Then run `.venv/bin/python -m uvicorn cardio_nb.api:app --host 127.0.0.1 --port 8000`.
The Next.js proxy uses MODEL_API_URL, defaulting to http://127.0.0.1:8000.

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
marks previous scores as stale until reassessment.
The latest submitted inputs are saved privately to the signed-in account;
exporting a JSON, CSV, or Excel assessment is an explicit user action. Every format contains only
the 55 labeled input values and the four output percentages. Excel uses
separate Inputs and Outputs sheets.

Feature selection remains intact. CAD uses 35 features, LAD 20, RCA 10, and
fixed LCX 54. Thus every nonconstant feature can affect at least one selected
model, but not every target. Exertional CP was constant and has zero learned
influence. Feature explanations are exact additive NB log-likelihood ratios
before probability calibration, not causal attributions. The all-input view
explicitly marks unselected fields. LCX probability is uncalibrated.

## Anatomy

72 original BodyParts3D OBJ meshes are served locally, with no runtime dependency
on the source server. Original alignment is preserved using a single transform.
LAD, LCX and RCA are selectable and have distinct, stable colors; predicted
probabilities remain numeric in the results panel.
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
node --test unit/assessment-export.test.mjs
APP_URL=http://127.0.0.1:3000 npx playwright test
```
