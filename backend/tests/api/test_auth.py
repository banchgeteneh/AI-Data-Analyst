from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.core.security import verify_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app, create_app
from app.models.user import User


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_database() -> Generator[None, None, None]:
    Base.metadata.create_all(TEST_ENGINE)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(TEST_ENGINE)


@asynccontextmanager
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.mark.anyio
async def test_registration_hashes_password_and_returns_safe_user() -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/auth/register",
            json={"name": "Example User", "email": "user@example.com", "password": "password123"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "user@example.com"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    with TestSessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "user@example.com"))
        assert user is not None
        assert user.password_hash != "password123"
        assert verify_password("password123", user.password_hash)


@pytest.mark.anyio
async def test_duplicate_email_is_rejected() -> None:
    async with client() as test_client:
        payload = {"name": "Example User", "email": "user@example.com", "password": "password123"}
        assert (await test_client.post("/api/v1/auth/register", json=payload)).status_code == 201
        response = await test_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


@pytest.mark.anyio
async def test_login_returns_jwt_and_me_requires_valid_token() -> None:
    async with client() as test_client:
        await test_client.post(
            "/api/v1/auth/register",
            json={"name": "Example User", "email": "user@example.com", "password": "password123"},
        )
        login = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        token = login.json()["access_token"]
        me = await test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        missing = await test_client.get("/api/v1/auth/me")
        invalid = await test_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert missing.status_code == 401
    assert invalid.status_code == 401


@pytest.mark.anyio
async def test_login_rejects_incorrect_credentials() -> None:
    async with client() as test_client:
        await test_client.post(
            "/api/v1/auth/register",
            json={"name": "Example User", "email": "user@example.com", "password": "password123"},
        )
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.anyio
async def test_production_cors_allows_vercel_registration_preflight() -> None:
    production_settings = Settings(
        _env_file=None,
        app_env="production",
        frontend_url="https://app.example.com",
        jwt_secret_key="a-random-production-secret-with-at-least-32-characters",
        mysql_password="safe-production-password",
        database_url="mysql+pymysql://user:password@db.example.com/analyst",
    )
    production_app = create_app(production_settings)
    transport = httpx.ASGITransport(app=production_app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        response = await test_client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "https://ai-data-analyst-phi.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ai-data-analyst-phi.vercel.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-credentials"] == "true"
