import pytest
from fastapi.testclient import TestClient
import app.core.database as database
import app.main as main

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    db_path = tmp_path / "julian-test.sqlite3"
    monkeypatch.setattr(database, "discover_database_path", lambda: db_path)
    database.initialize()
    return db_path

@pytest.fixture
def client(isolated_database):
    with TestClient(main.app) as test_client:
        yield test_client
