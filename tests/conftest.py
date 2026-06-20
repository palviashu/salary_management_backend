"""
Test configuration.

Uses a separate test database (salary_management_test) with the "begin once" pattern:
each test wraps in an outer transaction that rolls back after the test, so no data persists.
Service-level commit() calls become savepoint releases (not real commits) because we use
join_transaction_mode="create_savepoint".
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import create_app
from app.models.base import Base

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:password@127.0.0.1:5432/salary_management_test"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(test_engine) -> Session:
    """Each test gets a session in a rolled-back transaction — no data persists."""
    connection = test_engine.connect()
    transaction = connection.begin()
    # join_transaction_mode="create_savepoint" ensures that session.commit()
    # calls issue SAVEPOINT RELEASE instead of actual COMMIT, so the outer
    # transaction remains open and can be rolled back after the test.
    session = Session(connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """FastAPI test client with the DB dependency overridden to use the test session."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
