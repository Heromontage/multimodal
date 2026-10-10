"""Predict CAD and vessel outcomes from a CSV using locally trained models."""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .model import TARGETS


def predict_frame(frame, model_dir):
    # Labels are never model inputs, even if a caller supplies a labeled CSV.
    features = frame.drop(columns=list(TARGETS), errors='ignore')
    output = pd.DataFrame({'row_id': np.arange(len(frame))})
    for target in TARGETS:
        bundle = joblib.load(Path(model_dir) / f'{target}.joblib')
        model = bundle['model']
        calibration = bundle['calibration']
        p = (model.predict_proba(features)[:, 1] if calibration is None
             else calibration.predict(model.decision_function(features)))
        name = 'CAD' if target == 'Cath' else target
        output[f'{name}_probability'] = p
        output[f'{name}_prediction'] = (p >= bundle['threshold']).astype(int)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='CSV with the 55 original feature columns')
    parser.add_argument('--models', default='artifacts')
    parser.add_argument('--output', default='predictions.csv')
    args = parser.parse_args()
    result = predict_frame(pd.read_csv(args.input), args.models)
    result.to_csv(args.output, index=False)
    print(f'Saved {len(result)} patient predictions to {args.output}')


if __name__ == '__main__':
    main()
