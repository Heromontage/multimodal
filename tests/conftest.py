import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

@pytest.fixture
def auth_client(mail_outbox):
    from cardio_nb.api import app
    from cardio_nb.database import Base, get_db
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def database():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    client.mail_outbox = mail_outbox
    yield client, engine
    client.close()
    app.dependency_overrides.clear()
    engine.dispose()



@pytest.fixture
def mail_outbox(monkeypatch):
    from cardio_nb import auth
    outbox = []
    monkeypatch.setattr(auth, 'send_verification_email', lambda email, token: outbox.append((email, token)))
    return outbox
