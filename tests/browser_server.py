"""Isolated browser-test API. Never run this test harness as the application server."""
import os
import tempfile
from fastapi import HTTPException

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.NamedTemporaryFile(prefix='coronary-browser-', suffix='.db', delete=False).name
from cardio_nb import auth
from cardio_nb.api import app

outbox = {}
auth.send_verification_email = lambda email, token: outbox.__setitem__(email, token)

@app.get('/test-mail/{email}')
def test_mail(email: str):
    if email not in outbox:
        raise HTTPException(404)
    return {'token': outbox[email]}
