"""Local inference API. Uses existing model artifacts; never retrains on requests."""
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import math
import os

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import current_user, router as auth_router
from .database import User, get_db, initialize_database
from pydantic import BaseModel, ConfigDict

from .model import CONTINUOUS, TARGETS

ROOT = Path(os.environ.get('CARDIO_ROOT', Path(__file__).resolve().parents[1]))
ROUTING = {'CAD': 'Cath.joblib', 'LAD': 'LAD.joblib', 'LCX': 'fixed/LCX.joblib', 'RCA': 'RCA.joblib'}
GROUPS = {
    'Profile': ['Age', 'Sex', 'Weight', 'Length', 'BMI', 'Obesity'],
    'History': ['DM', 'HTN', 'Current Smoker', 'EX-Smoker', 'FH', 'CRF', 'CVA', 'Airway disease', 'Thyroid Disease', 'CHF', 'DLP'],
    'Symptoms': ['Typical Chest Pain', 'Atypical', 'Nonanginal', 'Exertional CP', 'LowTH Ang', 'Dyspnea', 'Function Class'],
    'Examination': ['BP', 'PR', 'Edema', 'Weak Peripheral Pulse', 'Lung rales', 'Systolic Murmur', 'Diastolic Murmur'],
    'ECG & echo': ['Q Wave', 'St Elevation', 'St Depression', 'Tinversion', 'LVH', 'Poor R Progression', 'BBB', 'EF-TTE', 'Region RWMA', 'VHD'],
    'Laboratory': ['FBS', 'CR', 'TG', 'LDL', 'HDL', 'BUN', 'ESR', 'HB', 'K', 'Na', 'WBC', 'Lymph', 'Neut', 'PLT'],
}
LABELS = {'Length': 'Height', 'DM': 'Diabetes mellitus', 'HTN': 'Hypertension',
    'FH': 'Family history', 'CRF': 'Chronic renal failure', 'CVA': 'Cerebrovascular accident',
    'CHF': 'Congestive heart failure', 'DLP': 'Dyslipidemia', 'EX-Smoker': 'Former smoker',
    'BP': 'Blood pressure', 'PR': 'Pulse rate', 'FBS': 'Fasting blood sugar',
    'CR': 'Creatinine', 'TG': 'Triglycerides', 'LDL': 'LDL cholesterol', 'HDL': 'HDL cholesterol',
    'BUN': 'Blood urea nitrogen', 'ESR': 'Sedimentation rate', 'HB': 'Hemoglobin',
    'K': 'Potassium', 'Na': 'Sodium', 'WBC': 'White blood cells', 'Lymph': 'Lymphocytes',
    'Neut': 'Neutrophils', 'PLT': 'Platelets', 'EF-TTE': 'Ejection fraction',
    'Region RWMA': 'RWMA region', 'VHD': 'Valvular heart disease', 'BBB': 'Bundle branch block',
    'LVH': 'Left ventricular hypertrophy', 'Tinversion': 'T-wave inversion',
    'St Elevation': 'ST elevation', 'St Depression': 'ST depression',
    'Exertional CP': 'Exertional chest pain', 'LowTH Ang': 'Low-threshold angina'}
# Units are displayed only where their interpretation is unambiguous; source-scale
# lab values without a data dictionary are explicitly marked as dataset units.
UNITS = {'Age': 'years', 'Weight': 'kg', 'Length': 'cm', 'BMI': 'kg/m²',
         'BP': 'mmHg', 'PR': 'bpm', 'EF-TTE': '%', 'Lymph': '%', 'Neut': '%'}


@lru_cache
def bundles():
    return {name: joblib.load(ROOT / 'artifacts' / path) for name, path in ROUTING.items()}


@lru_cache
def schema():
    data = pd.read_csv(ROOT / 'file.csv').drop(columns=list(TARGETS))
    metrics = pd.read_csv(ROOT / 'reports/summary.csv')
    fields = []
    for name in data:
        column = data[name]
        numeric = name in CONTINUOUS
        opts = sorted(column.unique().tolist()) if not numeric else None
        default = float(column.median()) if numeric else column.mode().iloc[0]
        if isinstance(default, np.generic):
            default = default.item()
        fields.append(dict(name=name, label=LABELS.get(name, name),
            group=next(group for group, names in GROUPS.items() if name in names),
            kind='number' if numeric else 'category', options=opts, default=default,
            unit=UNITS.get(name, 'dataset units' if numeric else ''),
            min=float(column.min()) if numeric else None,
            max=float(column.max()) if numeric else None,
            constant=column.nunique() == 1,
            used_by=[target for target, bundle in bundles().items() if name in bundle['model'].selected_features_]))
    targets = {}
    for target, bundle in bundles().items():
        metric = metrics[(metrics.target == ('Cath' if target == 'CAD' else target)) &
                         (metrics.model == ('fixed_mixed_nb' if target == 'LCX' else 'tuned_nb'))].iloc[0]
        targets[target] = dict(model='Fixed mixed NB' if target == 'LCX' else 'Tuned mixed NB',
            auc=float(metric.roc_auc_mean), threshold=float(bundle['threshold']),
            calibrated=bundle['calibration'] is not None,
            selected_features=bundle['model'].selected_features_)
    return dict(fields=fields, groups=list(GROUPS), targets=targets, patient_count=303,
        validation='5-fold nested cross-validation, repeated 3 times',
        selection_note='Model choices based on observed cross-validation results; external validation is still needed.')


class Patient(BaseModel):
    model_config = ConfigDict(extra='forbid')
    values: dict[str, object]


@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield


app = FastAPI(title='Coronary Atlas inference', docs_url='/docs', lifespan=lifespan)
app.include_router(auth_router)


@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ready', 'targets': list(bundles())}


@app.get('/schema')
def get_schema():
    return schema()


@app.post('/predict')
def predict(patient: Patient, user: User = Depends(current_user), db: Session = Depends(get_db)):
    fields = schema()['fields']
    expected = {f['name'] for f in fields}
    missing, extra = expected-set(patient.values), set(patient.values)-expected
    if missing or extra:
        raise HTTPException(422, dict(message='Supply exactly the 55 clinical inputs.',
                                      missing=sorted(missing), extra=sorted(extra)))
    errors, warnings, clean = {}, [], {}
    for f in fields:
        name, value = f['name'], patient.values[f['name']]
        if value is None:
            clean[name] = None
            warnings.append(f'{f["label"]}: missing; training imputation or neutral evidence used.')
        elif f['kind'] == 'number':
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1e6:
                errors[name] = 'Enter a finite, nonnegative numeric measurement below 1,000,000.'
            else:
                clean[name] = float(value)
                if value < f['min'] or value > f['max']:
                    warnings.append(f'{f["label"]} is outside the training range ({f["min"]:g}–{f["max"]:g}).')
        elif isinstance(value, (dict, list, bool)) or value not in f['options']:
            errors[name] = 'Choose one of the dataset categories.'
        else:
            clean[name] = value
    if errors:
        raise HTTPException(422, dict(message='Check the highlighted inputs.', fields=errors))
    x = pd.DataFrame([clean])
    predictions = {}
    for target, bundle in bundles().items():
        model = bundle['model']
        score = model.decision_function(x)
        calibration = bundle['calibration']
        p = float(model.predict_proba(x)[0, 1] if calibration is None else calibration.predict(score)[0])
        evidence = model.feature_log_odds(x).iloc[0].to_dict()
        features = [dict(name=f['name'], label=f['label'], value=clean[f['name']],
            used=f['name'] in evidence, contribution=float(evidence.get(f['name'], 0.))) for f in fields]
        features.sort(key=lambda item: -abs(item['contribution']))
        predictions[target] = dict(probability=p, positive=p >= bundle['threshold'],
            **schema()['targets'][target], features=features, prior_log_odds=float(model.prior_log_odds_))
    # Persist only after validation and all four models have completed successfully.
    user.saved_inputs = clean
    user.saved_at = datetime.utcnow()
    db.commit()
    return dict(predictions=predictions, warnings=warnings,
                explanation='Additive Naive Bayes log-odds before calibration; associations, not causal effects.')
