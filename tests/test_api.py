import importlib.util
import numpy as np
import pandas as pd


def client_and_schema(auth_client):
    assert importlib.util.find_spec('cardio_nb.api'), 'Prediction API has not been implemented'
    from fastapi.testclient import TestClient
    from cardio_nb.api import app
    client, _ = auth_client
    response = client.post('/signup', json={'email': 'api-tests@example.com', 'password': 'test-password-2026'})
    assert response.status_code == 201
    assert client.post('/verify-email', json={'token': client.mail_outbox[-1][1], 'password': 'test-password-2026'}).status_code == 200
    assert client.post('/signin', json={'email': 'api-tests@example.com', 'password': 'test-password-2026'}).status_code == 200
    response = client.get('/schema')
    assert response.status_code == 200
    return client, response.json()


def test_schema_covers_every_input_and_explains_constant_feature(auth_client):
    client, schema = client_and_schema(auth_client)
    from cardio_nb.model import TARGETS
    raw = pd.read_csv('file.csv')
    assert {f['name'] for f in schema['fields']} == set(raw) - set(TARGETS)
    assert len(schema['fields']) == 55
    constant = next(f for f in schema['fields'] if f['name'] == 'Exertional CP')
    assert constant['constant'] and constant['used_by'] == []


def test_predictions_match_selected_bundles_and_explanations_sum(auth_client):
    client, schema = client_and_schema(auth_client)
    import joblib
    values = {f['name']: f['default'] for f in schema['fields']}
    response = client.post('/predict', json={'values': values})
    assert response.status_code == 200, response.text
    result = response.json()
    for target in ['CAD', 'LAD', 'LCX', 'RCA']:
        path = 'artifacts/fixed/LCX.joblib' if target == 'LCX' else f'artifacts/{"Cath" if target == "CAD" else target}.joblib'
        bundle = joblib.load(path)
        x = pd.DataFrame([values])
        score = bundle['model'].decision_function(x)[0]
        expected = (bundle['model'].predict_proba(x)[0, 1] if bundle['calibration'] is None
                    else bundle['calibration'].predict(np.array([score]))[0])
        r = result['predictions'][target]
        assert np.isclose(r['probability'], expected)
        assert np.isclose(sum(f['contribution'] for f in r['features']) + r['prior_log_odds'], score)
        assert len(r['features']) == 55


def test_invalid_inputs_fail_without_silent_defaults(auth_client):
    client, schema = client_and_schema(auth_client)
    values = {f['name']: f['default'] for f in schema['fields']}
    assert client.post('/predict', json={'values': {}}).status_code == 422
    assert client.post('/predict', json={'values': values | {'Cath': 'CAD'}}).status_code == 422
    assert client.post('/predict', json={'values': values | {'Age': -1}}).status_code == 422
    assert client.post('/predict', json={'values': values | {'Sex': 'invalid'}}).status_code == 422
    response = client.post('/predict', json={'values': values | {'Age': None}})
    assert response.status_code == 200 and response.json()['warnings']
