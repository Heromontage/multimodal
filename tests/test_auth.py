import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PASSWORD = 'correct-horse-battery-2026'


def signup(client, email='person@example.com'):
    response = client.post('/signup', json={'email': email, 'password': PASSWORD})
    assert response.status_code == 201, response.text
    return response


def defaults(client):
    return {field['name']: field['default'] for field in client.get('/schema').json()['fields']}


def test_signup_hashes_password_and_uses_private_session_cookie(auth_client):
    from cardio_nb.database import User, LoginSession
    client, engine = auth_client
    response = signup(client, 'Person@example.com')
    assert response.json() == {'user': {'email': 'person@example.com'}, 'inputs': None}
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    with Session(engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith('$argon2')
        assert PASSWORD not in user.password_hash
        session = db.scalar(select(LoginSession))
        assert session.token_hash != client.cookies.get('coronary_session')


def test_assessment_saves_all_inputs_only_after_success_and_restores_them(auth_client):
    client, _ = auth_client
    signup(client)
    values = defaults(client) | {'Age': 58, 'Obesity': 'Y'}
    assert client.get('/session').json()['inputs'] is None
    response = client.post('/predict', json={'values': values})
    assert response.status_code == 200, response.text
    assert client.get('/session').json()['inputs'] == values
    invalid = values | {'Age': -1}
    assert client.post('/predict', json={'values': invalid}).status_code == 422
    assert client.get('/session').json()['inputs'] == values
    client.post('/signout')
    assert client.get('/session').status_code == 401
    assert client.post('/signin', json={'email': 'PERSON@example.com', 'password': PASSWORD}).status_code == 200
    assert client.get('/session').json()['inputs'] == values
    changed = values | {'Age': 65, 'FBS': None}
    assert client.get('/session').json()['inputs'] == values
    assert client.post('/predict', json={'values': changed}).status_code == 200
    assert client.get('/session').json()['inputs'] == changed


def test_users_cannot_access_each_others_inputs_and_signout_revokes_token(auth_client):
    client, _ = auth_client
    signup(client)
    values = defaults(client) | {'Age': 58}
    assert client.post('/predict', json={'values': values}).status_code == 200
    old_token = client.cookies.get('coronary_session')
    client.post('/signout')
    client.cookies.set('coronary_session', old_token)
    assert client.get('/session').status_code == 401
    client.cookies.clear()
    signup(client, 'second@example.com')
    assert client.get('/session').json()['inputs'] is None
    assert client.post('/predict', json={'values': defaults(client) | {'Age': 77}}).status_code == 200
    client.post('/signout')
    client.post('/signin', json={'email': 'person@example.com', 'password': PASSWORD})
    assert client.get('/session').json()['inputs'] == values


def test_authentication_validation_and_expired_sessions(auth_client):
    from cardio_nb.database import LoginSession
    client, engine = auth_client
    assert client.post('/predict', json={'values': defaults(client)}).status_code == 401
    assert client.post('/signup', json={'email': 'bad-email', 'password': PASSWORD}).status_code == 422
    assert client.post('/signup', json={'email': 'person@example.com', 'password': 'short'}).status_code == 422
    signup(client)
    assert client.post('/signup', json={'email': 'person@example.com', 'password': PASSWORD}).status_code == 409
    client.post('/signout')
    assert client.post('/signin', json={'email': 'person@example.com', 'password': 'wrong-password'}).status_code == 401
    assert client.post('/signin', json={'email': 'person@example.com', 'password': PASSWORD}).status_code == 200
    with Session(engine) as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get('/session').status_code == 401


def test_repeated_wrong_passwords_are_limited(auth_client):
    client, _ = auth_client
    signup(client)
    client.post('/signout')
    for _ in range(5):
        client.post('/signin', json={'email': 'person@example.com', 'password': 'wrong-password'})
    response = client.post('/signin', json={'email': 'person@example.com', 'password': PASSWORD})
    assert response.status_code == 429


def test_inference_failure_does_not_overwrite_saved_inputs(auth_client, monkeypatch):
    from cardio_nb import api
    client, _ = auth_client
    signup(client)
    values = defaults(client) | {'Age': 58}
    assert client.post('/predict', json={'values': values}).status_code == 200
    def failed_models():
        raise RuntimeError('model unavailable')
    monkeypatch.setattr(api, 'bundles', failed_models)
    with pytest.raises(RuntimeError, match='model unavailable'):
        client.post('/predict', json={'values': values | {'Age': 66}})
    assert client.get('/session').json()['inputs'] == values
