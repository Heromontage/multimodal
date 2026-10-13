import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

@pytest.fixture
def auth_client():
    from cardio_nb.api import app
    from cardio_nb.database import Base, get_db
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def database():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    yield client, engine
    client.close()
    app.dependency_overrides.clear()
    engine.dispose()

