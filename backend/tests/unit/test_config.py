import pytest

from app.config import Settings


def test_settings_load_foundation_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "AI Data Analyst API"
    assert settings.max_dataset_size_mb == 250
    assert settings.database_url.startswith("mysql+pymysql://")


def test_postgresql_url_uses_psycopg_without_changing_pooler_identity() -> None:
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql://postgres.project-ref:p%40ssword"
            "@aws-0-eu-west-2.pooler.supabase.com:5432/postgres"
        ),
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "postgres.project-ref" in settings.database_url
    assert "p%40ssword@" in settings.database_url


def test_mysql_url_without_driver_uses_pymysql() -> None:
    settings = Settings(_env_file=None, database_url="mysql://user:password@localhost/analyst")

    assert settings.database_url.startswith("mysql+pymysql://")


def test_production_settings_reject_mysql_database_url() -> None:
    with pytest.raises(ValueError, match="PostgreSQL with the psycopg driver") as error:
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            jwt_secret_key="a-random-production-secret-with-at-least-32-characters",
            database_url="mysql+pymysql://user:sensitive-test-password@db.example.com/analyst",
        )

    assert "sensitive-test-password" not in str(error.value)


def test_groq_model_default_uses_supported_generation_model() -> None:
    settings = Settings(_env_file=None)

    assert settings.groq_model == "openai/gpt-oss-120b"


def test_development_settings_allow_both_frontend_origins() -> None:
    settings = Settings(_env_file=None, app_env="development", frontend_url="http://localhost:5173")

    assert settings.allowed_frontend_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_non_development_settings_only_allow_configured_origins() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        frontend_url="https://app.example.com/",
        frontend_origins="https://admin.example.com, https://app.example.com/",
        jwt_secret_key="a-random-production-secret-with-at-least-32-characters",
        mysql_password="safe-production-password",
        database_url="postgresql://analyst:safe-production-password@db.example.com/analyst",
    )

    assert settings.allowed_frontend_origins == [
        "https://app.example.com",
        "https://admin.example.com",
        "https://ai-data-analyst-phi.vercel.app",
    ]


def test_production_settings_reject_default_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            jwt_secret_key="change-me",
            mysql_password="safe-production-password",
            database_url="mysql+pymysql://analyst:safe-production-password@db.example.com/analyst",
        )


def test_production_settings_reject_debug_mode() -> None:
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=True,
            jwt_secret_key="a-random-production-secret-with-at-least-32-characters",
            mysql_password="safe-production-password",
            database_url="mysql+pymysql://analyst:safe-production-password@db.example.com/analyst",
        )


def test_unknown_environment_cannot_bypass_production_validation() -> None:
    with pytest.raises(ValueError, match="APP_ENV"):
        Settings(_env_file=None, app_env="prodution", debug=True, jwt_secret_key="change-me")


def test_production_settings_reject_localhost_frontend_origin() -> None:
    with pytest.raises(ValueError, match="HTTPS origins"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            frontend_url="http://localhost:5173",
            jwt_secret_key="a-random-production-secret-with-at-least-32-characters",
            database_url="postgresql://analyst:safe-production-password@db.example.com/analyst",
        )


def test_production_settings_reject_short_upload_and_token_limits() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, max_dataset_size_mb=251)
    with pytest.raises(ValueError):
        Settings(_env_file=None, jwt_access_token_expire_minutes=0)
