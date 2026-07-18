import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.main import app
from app import models


@pytest.fixture(scope="function")
def client():
    models.Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    models.Base.metadata.drop_all(bind=engine)
