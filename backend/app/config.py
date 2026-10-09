from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "AI Data Analyst API"
    app_env: str = "development"
    debug: bool = False

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    frontend_origins: str = ""

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "ai_data_analyst"
    mysql_user: str = "ai_data_analyst"
    mysql_password: str = "change-me"
    database_url: str = "mysql+pymysql://ai_data_analyst:change-me@localhost:3306/ai_data_analyst"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    max_dataset_size_mb: int = Field(default=250, ge=1, le=250)
    upload_directory: str = "./storage/uploads"
    jwt_secret_key: str = "change-me"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        environment = self.app_env.strip().lower()
        if environment not in {"development", "dev", "test", "production", "prod"}:
            raise ValueError("APP_ENV must be development, test, or production")
        self.app_env = environment
        if environment not in {"production", "prod"}:
            return self

        if self.debug:
            raise ValueError("DEBUG must be disabled in production")
        if len(self.jwt_secret_key) < 32 or self.jwt_secret_key.strip().lower() in {"change-me", "replace-with-a-long-random-secret"}:
            raise ValueError("JWT_SECRET_KEY must be a unique random value of at least 32 characters in production")
        if "change-me" in self.database_url.lower():
            raise ValueError("Production database credentials must be configured")
        for origin in self.allowed_frontend_origins:
            parsed = urlsplit(origin)
            hostname = (parsed.hostname or "").casefold()
            if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
                raise ValueError("Production frontend origins must be explicit HTTPS origins")
            if hostname in {"localhost", "127.0.0.1", "::1"} or "*" in origin:
                raise ValueError("Production frontend origins cannot be local or wildcard origins")
        return self

    @property
    def allowed_frontend_origins(self) -> list[str]:
        configured = [self.frontend_url, *self.frontend_origins.split(",")]
        environment = self.app_env.strip().lower()
        if environment in {"development", "dev"}:
            configured.extend(("http://localhost:5173", "http://127.0.0.1:5173"))
        elif environment in {"production", "prod"}:
            configured.append("https://ai-data-analyst-phi.vercel.app")

        origins: list[str] = []
        for origin in configured:
            normalized = origin.strip().rstrip("/")
            if normalized and normalized not in origins:
                origins.append(normalized)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
