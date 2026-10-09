"""
Shared pytest fixtures.

Each test runs against the atoma_test PostgreSQL database, which is
dropped and recreated per test session. Redis keys used by tests are
prefixed with test: and cleaned up after each test.
"""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.auth import hash_password, create_token
from app.main import app
from app import models

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL not set in .env. "
        "Add: TEST_DATABASE_URL=postgresql://postgres:...@localhost:5432/atoma_test"
    )


# --------------------------------------------------
# DATABASE FIXTURES
# --------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Session-wide engine to the test DB. Drops and recreates tables."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Per-test session. Rolls back after each test."""
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(engine, db_session):
    """
    FastAPI TestClient with get_db overridden to use the test session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by the fixture

    app.dependency_overrides[get_db] = override_get_db

    # Clean tables before each test
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --------------------------------------------------
# SEEDED USER FIXTURES
# --------------------------------------------------

def _create_user(db, name, email, password, role, location):
    user = models.User(
        name=name,
        email=email,
        password=hash_password(password),
        role=role,
        location=location,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def customer(db_session):
    return _create_user(
        db_session,
        "Test Customer",
        "customer@test.com",
        "password123",
        "user",
        "Mumbai",
    )


@pytest.fixture
def beautician_user(db_session):
    return _create_user(
        db_session,
        "Test Beautician",
        "beautician@test.com",
        "password123",
        "beautician",
        "Mumbai",
    )


@pytest.fixture
def admin_user(db_session):
    return _create_user(
        db_session,
        "Test Admin",
        "admin@test.com",
        "password123",
        "admin",
        "Mumbai",
    )


@pytest.fixture
def beautician(db_session, beautician_user):
    """A Beautician profile linked to beautician_user."""
    b = models.Beautician(
        user_id=beautician_user.id,
        name="Test Beautician",
        location="Mumbai",
        is_available=True,
    )
    db_session.add(b)
    db_session.commit()
    db_session.refresh(b)
    return b


@pytest.fixture
def service(db_session):
    s = models.Service(
        name="Hair Styling",
        description="Test service",
        price=500,
        duration=45,
        is_active=True,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def inactive_service(db_session):
    s = models.Service(
        name="Old Service",
        description="Inactive",
        price=500,
        duration=45,
        is_active=False,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


# --------------------------------------------------
# TOKEN FIXTURES
# --------------------------------------------------

@pytest.fixture
def customer_token(customer):
    return create_token({"sub": customer.email, "role": customer.role})


@pytest.fixture
def beautician_token(beautician_user):
    return create_token(
        {"sub": beautician_user.email, "role": beautician_user.role}
    )


@pytest.fixture
def admin_token(admin_user):
    return create_token({"sub": admin_user.email, "role": admin_user.role})