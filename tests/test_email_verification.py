from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

CREDS = {'email': 'verify@example.com', 'password': 'test-password-2026'}


def test_signup_cannot_login_before_verification(auth_client):
    client, _ = auth_client
    response = client.post('/signup', json=CREDS)
    assert response.status_code == 201
    assert response.json()['verification_required'] is True
    assert 'set-cookie' not in response.headers
    assert client.get('/session').status_code == 401
    assert client.post('/signin', json=CREDS).status_code == 403


def test_verification_is_single_use_and_requires_password(auth_client, mail_outbox):
    from cardio_nb.database import EmailVerification, LoginSession
    client, engine = auth_client
    client.post('/signup', json=CREDS)
    token = mail_outbox[-1][1]
    with Session(engine) as db:
        record = db.scalar(select(EmailVerification))
        assert record.token_hash != token
        assert db.scalar(select(LoginSession)) is None
    assert client.post('/verify-email', json={'token': token, 'password': 'wrong-password'}).status_code == 400
    assert client.post('/verify-email', json={'token': token, 'password': CREDS['password']}).status_code == 200
    assert client.get('/session').status_code == 401
    assert client.post('/verify-email', json={'token': token, 'password': CREDS['password']}).status_code == 400
    assert client.post('/signin', json=CREDS).status_code == 200


def test_expiry_resend_and_old_link_revocation(auth_client, mail_outbox):
    from cardio_nb.database import EmailVerification
    client, engine = auth_client
    client.post('/signup', json=CREDS)
    old = mail_outbox[-1][1]
    assert client.post('/resend-verification', json={'email': CREDS['email']}).status_code == 200
    assert len(mail_outbox) == 1
    with Session(engine) as db:
        record = db.scalar(select(EmailVerification))
        record.expires_at = datetime.utcnow() - timedelta(seconds=1)
        record.sent_at = datetime.utcnow() - timedelta(minutes=2)
        db.commit()
    assert client.post('/verify-email', json={'token': old, 'password': CREDS['password']}).status_code == 400
    assert client.post('/resend-verification', json={'email': CREDS['email']}).status_code == 200
    new = mail_outbox[-1][1]
    assert new != old
    assert client.post('/verify-email', json={'token': old, 'password': CREDS['password']}).status_code == 400
    assert client.post('/verify-email', json={'token': new, 'password': CREDS['password']}).status_code == 200
    count = len(mail_outbox)
    known = client.post('/resend-verification', json={'email': CREDS['email']})
    unknown = client.post('/resend-verification', json={'email': 'unknown@example.com'})
    assert known.json() == unknown.json()
    assert len(mail_outbox) == count


def test_email_failure_does_not_create_account(auth_client, monkeypatch):
    from cardio_nb import auth
    from cardio_nb.database import User
    client, engine = auth_client
    def fail(*args):
        raise RuntimeError('delivery failed')
    monkeypatch.setattr(auth, 'send_verification_email', fail)
    assert client.post('/signup', json=CREDS).status_code == 503
    with Session(engine) as db:
        assert db.scalar(select(User)) is None


def test_existing_account_and_session_require_verification(auth_client, mail_outbox):
    from cardio_nb.auth import password_hasher, token_hash
    from cardio_nb.database import User, LoginSession
    client, engine = auth_client
    with Session(engine) as db:
        user = User(email=CREDS['email'], password_hash=password_hasher.hash(CREDS['password']), saved_inputs={'Age': 58})
        db.add(user)
        db.flush()
        db.add(LoginSession(user_id=user.id, token_hash=token_hash('old-session'), expires_at=datetime.utcnow()+timedelta(days=1)))
        db.commit()
    client.cookies.set('coronary_session', 'old-session')
    assert client.get('/session').status_code == 401
    assert client.post('/signin', json=CREDS).status_code == 403
    assert client.post('/resend-verification', json={'email': CREDS['email']}).status_code == 200
    assert client.post('/verify-email', json={'token': mail_outbox[-1][1], 'password': CREDS['password']}).status_code == 200
    assert client.get('/session').status_code == 401
    assert client.post('/signin', json=CREDS).json()['inputs'] == {'Age': 58}


def test_smtp_configuration_fails_closed(monkeypatch):
    from cardio_nb.mail import send_verification_email
    monkeypatch.delenv('SMTP_USERNAME', raising=False)
    monkeypatch.delenv('SMTP_PASSWORD', raising=False)
    with pytest.raises(RuntimeError, match='not configured'):
        send_verification_email('recipient@example.com', 'secret-token')


def test_smtp_uses_tls_and_sends_expiring_link(monkeypatch):
    from cardio_nb.mail import send_verification_email
    import smtplib
    import ssl
    delivered = []
    class SMTP:
        def __init__(self, host, port, context, timeout):
            assert host == 'smtp.gmail.com' and port == 465
            assert context.verify_mode == ssl.CERT_REQUIRED
            assert context.check_hostname
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def login(self, username, password):
            assert username == 'sender@gmail.com' and password == 'abcdefghijklmnop'
        def send_message(self, message):
            delivered.append(message)
            return {}
    monkeypatch.setattr(smtplib, 'SMTP_SSL', SMTP)
    monkeypatch.setenv('SMTP_USERNAME', 'sender@gmail.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'abcd efgh ijkl mnop')
    monkeypatch.setenv('APP_BASE_URL', 'https://atlas.example.com')
    send_verification_email('recipient@example.com', 'one-time-secret')
    message = delivered[0]
    assert message['To'] == 'recipient@example.com'
    assert message['From'] == 'sender@gmail.com'
    assert 'https://atlas.example.com/verify-email#token=one-time-secret' in message.get_content()
    assert '30 minutes' in message.get_content()


def test_resends_stop_after_five_per_hour(auth_client, mail_outbox):
    from cardio_nb.database import EmailVerification
    client, engine = auth_client
    client.post('/signup', json=CREDS)
    for _ in range(7):
        with Session(engine) as db:
            record = db.scalar(select(EmailVerification))
            record.sent_at = datetime.utcnow()-timedelta(minutes=2)
            db.commit()
        client.post('/resend-verification', json={'email': CREDS['email']})
    assert len(mail_outbox) == 5
    assert client.post('/verify-email', json={'token': mail_outbox[-1][1], 'password': CREDS['password']}).status_code == 200


def test_failed_resend_keeps_previous_link_valid(auth_client, mail_outbox, monkeypatch):
    from cardio_nb import auth
    from cardio_nb.database import EmailVerification
    client, engine = auth_client
    client.post('/signup', json=CREDS)
    old = mail_outbox[-1][1]
    with Session(engine) as db:
        record = db.scalar(select(EmailVerification))
        record.sent_at = datetime.utcnow()-timedelta(minutes=2)
        db.commit()
    def fail(*args):
        raise RuntimeError('mail unavailable')
    monkeypatch.setattr(auth, 'send_verification_email', fail)
    assert client.post('/resend-verification', json={'email': CREDS['email']}).status_code == 503
    assert client.post('/verify-email', json={'token': old, 'password': CREDS['password']}).status_code == 200


def test_verification_password_attempts_are_limited(auth_client, mail_outbox):
    client, _ = auth_client
    client.post('/signup', json=CREDS)
    token = mail_outbox[-1][1]
    for _ in range(5):
        assert client.post('/verify-email', json={'token': token, 'password': 'wrong-password'}).status_code == 400
    assert client.post('/verify-email', json={'token': token, 'password': CREDS['password']}).status_code == 429
    assert client.get('/session').status_code == 401
