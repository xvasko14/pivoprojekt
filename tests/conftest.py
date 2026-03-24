import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    import database
    database.create_tables()
    yield db_path


@pytest.fixture
def client(test_db):
    import importlib
    import main
    importlib.reload(main)
    from main import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def sample_event():
    import database
    return database.create_event(
        place="Hostinec U Karla",
        event_date="2099-12-31",
        event_time="19:00",
        description="Testovaci event",
    )
