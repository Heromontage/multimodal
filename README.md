# Coronary Atlas

Coronary Atlas is a research and education app that uses four **Naive Bayes** machine-learning models to estimate whether a person's recorded findings resemble cases of coronary artery disease (CAD) in a small historical dataset. It combines a 55-field assessment form, model explanations, and an interactive reference heart.

**If you are new to this topic:** Coronary arteries supply blood to the heart muscle. CAD means disease of these arteries; *stenosis* means narrowing. The app accepts findings such as age, symptoms, examination results, and laboratory measurements. It produces one estimate for overall CAD and one for narrowing in each of three major arteries. These estimates are **research outputs, not diagnoses**. A high number does not locate a blockage, and a low number does not rule one out. Clinical assessment and appropriate diagnostic tests remain necessary.

[Try the live frontend](https://multimodal-qwc2.vercel.app). Its Python API runs on Render and its MySQL-compatible database on TiDB Cloud. This repository also contains the training code, saved models, validation results, and a local Docker setup.

## What the app does

1. **Creates an account and verifies email.** Signup sends a single-use link. The recipient opens it and enters the account password to confirm mailbox access. Unverified accounts cannot sign in.
2. **Collects 55 findings.** The form groups inputs into profile, history, symptoms, examination, ECG/echo, and laboratory sections. Initial values come from dataset medians or modes. They are reference defaults, **not a real patient**.
3. **Runs four saved models.** The API validates inputs and loads trained model files. It does not retrain during a request.
4. **Shows percentages and flags.** Each model gives a number between 0 and 1, displayed as a percentage. A saved threshold turns that number into a positive or negative flag.
5. **Shows an explanation and a reference heart.** Selected findings have additive contributions to each model's score. These are associations, not causes. The BodyParts3D heart is generic anatomy, not a scan of the assessed person or a lesion map.
6. **Remembers the latest inputs.** The database stores the signed-in account's most recently submitted 55 values. A user may explicitly export an assessment as CSV, Excel, or JSON. Predictions are calculated on demand; the database does not keep a history of them.

## The four questions the models answer

| App result | Training label | Positive label | Meaning |
| --- | --- | --- | --- |
| CAD | Cath | CAD | Overall coronary disease label |
| LAD | LAD | Stenotic | Narrowing of the left anterior descending artery |
| LCX | LCX | Stenotic | Narrowing of the left circumflex artery |
| RCA | RCA | Stenotic | Narrowing of the right coronary artery |

Each target has its **own** model. None of these four outcome columns is an input to any model. The overall CAD output is learned from the Cath label; it is not calculated from the three vessel outputs. One supplied row has an overall/vessel-label disagreement. The training code preserves it and records it in the audit instead of inventing a corrected label.

The supplied [dataset](file.csv) has **303 rows**, **55 input columns**, and four outcome columns. Positive counts are 216 for Cath, 177 for LAD, 119 for LCX, and 114 for RCA. It has no missing cells or duplicate input rows. One input, Exertional CP, is constant and therefore has no learned influence in the mixed models. No patient, hospital, or date identifier was supplied for grouping rows or checking changes across sites and time. **This repository does not establish permission to redistribute the patient-level CSV. Check its provenance and permissions before making the repository public.**

### Naive Bayes in plain language

A Naive Bayes model starts with how often an outcome occurred in training. It then asks whether each selected finding was more common among positive or negative cases. Each finding moves the score up or down. The implementation adds these pieces of evidence as *log odds* and converts the total into a number between 0 and 1.

The “naive” assumption is that findings are independent **after the outcome is known**. Real findings can be correlated, so this is an approximation. Raw output numbers are not automatically reliable probabilities.

This project compares three approaches:

| Approach | How it handles findings | Purpose |
| --- | --- | --- |
| Ordinary Gaussian Naive Bayes | Converts categories to indicator columns and models numeric values with Gaussian curves | Baseline |
| Fixed mixed Naive Bayes | Models numeric values with Gaussian curves and categories with smoothed frequency tables | Predefined alternative |
| Tuned mixed Naive Bayes | Searches numeric treatments, smoothing, variance sharing, and feature counts | Selected inside cross-validation |

The mixed model can use Gaussian numeric likelihoods, a quantile transformation followed by Gaussian likelihoods, or numeric bins. Categories use smoothing so rare values do not get zero probability. Missing numeric values use medians learned from training data. A category unseen during training gives neutral evidence. Feature selection ranks associations **within the training fold**, then chooses 10, 20, 35, or all informative features. The search contains **48 predefined configurations**. See [the model implementation](cardio_nb/model.py) and [the experiment code](cardio_nb/experiment.py).

Tuned models also learn a monotone sigmoid calibration from training-only held-out scores. Calibration tries to make displayed percentages better match observed frequencies; it does not improve ROC-AUC by itself. Training-only scores also select a threshold that maximizes *balanced accuracy*, which balances sensitivity and specificity. The fixed LCX model used by the web app is **uncalibrated** and uses a 0.5 threshold. Its displayed percentage is not a clinically validated chance of stenosis.

### How the models were evaluated

The main experiment uses **nested cross-validation** so each evaluated row is predicted by a model that did not train on it:

1. The **outer** evaluation divides rows into five stratified folds and repeats this three times with predefined seeds. This produces 15 held-out evaluations per target.
2. Within each outer training portion, **four inner folds** choose a tuned configuration. Imputation, transformations, category statistics, feature selection, calibration, and threshold selection stay inside the training portion.
3. The selected process predicts the untouched outer held-out portion. Those predictions form the evaluation.
4. After evaluation, final models are fitted on all 303 rows and saved for the app. These final fits have **no independent test score** of their own.

The primary metric is **ROC-AUC**, which measures how well positive examples rank above negative examples. About 0.5 means chance ranking; 1.0 means perfect ranking on the evaluated data. AUC does not tell you whether a displayed percentage is accurate. The report also includes accuracy, precision, recall, specificity, F1, balanced accuracy, Brier score, and log loss. See [full results and limitations](reports/results.md) and the [frozen experiment plan](docs/experiment_plan.md).

| Target | Baseline AUC | Fixed mixed AUC | Tuned mixed AUC | Web app choice | AUC for that choice |
| --- | ---: | ---: | ---: | --- | ---: |
| CAD | 0.8507 | 0.9090 | 0.9208 | Tuned | 0.9208 |
| LAD | 0.7955 | 0.8380 | 0.8427 | Tuned | 0.8427 |
| LCX | 0.6207 | 0.7167 | 0.6798 | Fixed mixed | 0.7167 |
| RCA | 0.6385 | 0.7157 | 0.7222 | Tuned | 0.7222 |

These are **mean held-out outer-fold AUCs** on this dataset, not a guarantee for a new person or hospital. The web app chooses fixed LCX because its observed AUC was higher while using tuned models for the other targets. That combined deployment choice was made after looking at the comparison and has **not** been independently evaluated as one new policy. LAD/RCA differences are small; LCX/RCA discrimination is modest. The data does not establish clinical readiness.

## How the software fits together

~~~text
Browser
  └─ Next.js frontend on Vercel
       ├─ form, anatomy, explanations, and exports
       ├─ same-origin /api/... proxy
       │    └─ FastAPI backend on Render
       │         ├─ saved Naive Bayes model bundles
       │         └─ TiDB Cloud database: accounts and latest inputs
       └─ protected email relay sends verification mail through Gmail
~~~

The browser sends account and prediction requests to the frontend's same-origin API routes. The frontend forwards allowed requests to Python. Database credentials and the email-relay token stay in server-side settings, not browser code. The API loads saved models from [artifacts](artifacts/). It reads [file.csv](file.csv) for form choices and reference ranges and [reports/summary.csv](reports/summary.csv) for the model-information display. Those are **runtime dependencies**, not removable training leftovers. The API creates its account tables on startup if they do not exist.

### Accounts and saved inputs

Signup validates email *syntax*. The verification link proves access to the mailbox, which syntax alone cannot do. The link expires after 30 minutes. Resends are limited to once per minute and five per hour per account. Passwords are stored as Argon2 hashes; verification and login tokens are stored as hashes. Sessions use HttpOnly, SameSite cookies, expire after seven days, and are revoked on signout. Repeated wrong passwords temporarily lock the account. See [authentication code](cardio_nb/auth.py).

The database stores email addresses, password hashes, session and verification records, and each account's latest 55 inputs. These inputs can be sensitive health information. Treat the database and exports accordingly. **A free hackathon deployment should use synthetic or properly authorized and deidentified demonstrations. This project has not established the controls or clinical validation needed for real-patient care.** Never commit a local .env file, database dump, credential, or patient export.

In the deployed setup, Render sends an authenticated HTTPS request to a protected Vercel route for verification email. That route uses Gmail SMTP. The same MAIL_RELAY_TOKEN must be set on both services, while the Gmail address and app password belong on Vercel only. The local Docker setup can send SMTP directly.

### Anatomy and explanations

The frontend serves selected BodyParts3D OBJ heart and artery meshes. Users can rotate and zoom the heart; LAD, LCX, and RCA have distinct colors. The colors identify structures and do **not** show measured narrowing or lesion locations. [Anatomy sources and licensing](docs/anatomy-sources.md) lists the official asset URLs, identifiers, hashes, and attribution.

For each result, the explanation starts with the learned class balance and lists each selected feature's additive contribution to the model's log odds. An unused feature has zero contribution for that target. This explains **what the model calculated**, not why a person has disease. Contributions are calculated before probability calibration.

## Try the running app

Open the [frontend](https://multimodal-qwc2.vercel.app), sign up, verify email, and sign in. The [backend health endpoint](https://multimodal-tzyq.onrender.com/health) checks the database and model bundles. A free Render service can take time to wake after inactivity, so the first request may be slower.

**Use synthetic test inputs for a demo.** The form's starting values are dataset reference values, not a complete synthetic patient or a recommendation. Confirm an input's original scale before entering it. Some laboratory measurements lack a trustworthy unit dictionary in the source and are labeled “dataset units” in the UI.

## Run locally with Docker

You need Docker with Compose, a working verification-email sender, and an available port 3000. Run these commands from the repository root:

~~~bash
python scripts/configure_database.py
~~~

This creates random MySQL credentials in the ignored local .env file without replacing existing ones. Add SMTP_USERNAME and SMTP_PASSWORD to .env; use a Gmail app password if using Gmail. See the [.env example](.env.example). Keep APP_BASE_URL=http://localhost:3000 and COOKIE_SECURE=false for local HTTP.

~~~bash
docker compose up --build -d
~~~

Open <http://localhost:3000>. Compose runs MySQL 8.4, FastAPI, and Next.js. Only the frontend is published, on the computer's loopback interface. MySQL data survives docker compose down in the named mysql-data volume. **docker compose down -v deletes local accounts and saved inputs.** For separate development ports, see the [frontend guide](docs/frontend.md).

## Reproduce training and predict from a CSV

Use Python 3.11 and the pinned [requirements](requirements.txt). Training runs on CPU and may take time because it repeats the model search for all four outcomes.

~~~bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m cardio_nb.experiment --jobs 4
~~~

The experiment reads file.csv, writes evaluation and audit files to reports/, and saves final model bundles to artifacts/. The default seed and fold counts are in the [experiment plan](docs/experiment_plan.md). Each .joblib bundle contains the fitted model, calibration if applicable, threshold, feature names, and a dataset fingerprint. Load .joblib files only from trusted sources: Python deserialization can execute code.

To predict from another CSV, supply **the same 55 named inputs and original data scales**. Extra outcome columns are ignored. Missing required columns fail clearly. Blank values can be imputed, while unfamiliar categorical spellings give neutral evidence. The command-line tool defaults to the *all-tuned* artifacts/ directory; the web API uses the per-target choices above.

~~~bash
.venv/bin/python -m cardio_nb.predict --input new_patients.csv --output predictions.csv
~~~

The output contains a row ID, four percentages, and four binary flags (1 means CAD or stenosis according to that model's saved threshold). Keep input and output CSVs private if they contain health information.

## Deploy the current three-service setup

The current setup uses Vercel for the frontend, Render for the Python web service, and TiDB Cloud for a MySQL-compatible database. Create the database first and obtain a **TLS-verified** connection URL. Put credentials only in hosting environment settings, never Git or a browser-visible NEXT_PUBLIC_ variable. DATABASE_URL uses the mysql+pymysql driver with the correct TiDB host, port, database, username, and URL-encoded password. Its CA path must exist inside the Render environment; a literal placeholder such as <CA_PATH> will not work.

| Service | Variable | Purpose |
| --- | --- | --- |
| Render API | DATABASE_URL | TLS-verified TiDB/MySQL connection |
| Render API | APP_BASE_URL | Public HTTPS frontend URL for email links |
| Render API | COOKIE_SECURE=true | HTTPS-only session cookie |
| Render API | MAIL_RELAY_TOKEN | Random shared email-relay secret, at least 32 characters |
| Render API | PYTHON_VERSION | Compatible Python version; tested with 3.11 |
| Vercel frontend | MODEL_API_URL | Public HTTPS Render API URL |
| Vercel frontend | MAIL_RELAY_TOKEN | Same value as Render |
| Vercel frontend | SMTP_USERNAME | Gmail sender address |
| Vercel frontend | SMTP_PASSWORD | Gmail app password; server-side secret |

On Render, deploy the naive_bayes branch as a Python web service from the **repository root**. Build with pip install -r requirements-api.txt and start with uvicorn cardio_nb.api:app --host 0.0.0.0 --port $PORT. On Vercel, deploy the same branch with **Root Directory** set to frontend. MODEL_API_URL should be the Render base URL, without a trailing /health. The API creates empty account tables at startup; do not import local accounts or patient data into a demo database.

After deployment, check /health on Render, load the Vercel site, complete signup and email verification, sign in, and run a synthetic assessment. Keep the database URL and SMTP credentials out of screenshots and issues. After rotating a credential, update the appropriate hosting setting and redeploy.

Render Free can spin down after inactivity. A scheduler may request the lightweight /docs URL periodically for a demo, but this does not guarantee availability. Check current provider usage limits. Free hosting, unverified source-data rights, and lack of external clinical validation make this setup unsuitable for real-patient production use.

## Repository map and cleanup

| Path | Purpose |
| --- | --- |
| cardio_nb/ | Model, training, calibration, API, authentication, database, and email code |
| frontend/ | Next.js UI, proxy, email relay, anatomy meshes, and frontend checks |
| artifacts/ | Saved tuned and fixed model bundles; web API uses tuned CAD/LAD/RCA and fixed LCX |
| file.csv | Original 303-row dataset; needed by API form schema and experiment |
| reports/ | Held-out results, fold and patient predictions, audit, plots; summary.csv is needed by API |
| docs/ | Experiment plan, frontend development notes, and anatomy attribution |
| tests/ | Python model and API tests |
| compose.yaml, compose.dev.yaml, Dockerfile.api, frontend/Dockerfile | Local Docker setup |

The large reports/oof_predictions.csv, reports/inner_search.csv, and reports/splits.json files are kept for reproducibility and audit. Fixed model bundles are kept for comparisons and the command-line --models artifacts/fixed option. Local virtual environments, node_modules, Next.js builds, browser-test output, and .env are ignored by Git. The old Oracle VM deployment files were removed because they do not describe this deployment.

## Important limits

- **Small, single dataset:** 303 rows cannot establish performance at another hospital, in a different population, or at a later date. There is no independent external validation.
- **Not a clinical tool:** AUCs describe a research experiment. The models are not validated for screening, triage, diagnosis, or treatment decisions. LCX/RCA ranking is modest and LCX percentages are uncalibrated.
- **Input timing and units:** Some findings may be available only after clinical workup. Source-scale laboratory units are not fully documented.
- **Explanations are associations:** A feature contribution is a likelihood calculation, not a causal medical explanation.
- **Privacy and permissions:** The tracked CSV is patient-level data with unverified redistribution permission. The database can hold new health inputs. Review data rights and privacy controls before public-repository or real-patient use.
- **No guaranteed uptime on free hosts:** Deployment or periodic pings do not establish availability or data-protection guarantees.

For exact metrics and uncertainty caveats, read the [results report](reports/results.md). For detailed local development, authentication, and UI behavior, read the [frontend guide](docs/frontend.md).
