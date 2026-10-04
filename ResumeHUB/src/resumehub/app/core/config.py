from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-me"
DEFAULT_ADMIN_PASSWORD = "change-me-now"
API_PREFIX = "/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HUB_", extra="ignore")

    env: str = "dev"
    app_name: str = "Resume Hub"
    docs_enabled: bool = True
    cors_origins: list[str] = []

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "resume_hub"
    resume_collection: str = "resumes"
    role_collection: str = "roles"
    resume_files_dir: str | None = None

    jwt_secret: str = DEFAULT_SECRET
    jwt_alg: str = "HS256"
    access_ttl_min: int = 30
    refresh_ttl_days: int = 7
    login_max_attempts: int = 5
    login_window_sec: int = 900

    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = DEFAULT_ADMIN_PASSWORD

    # None = every discovered module. "auth" and "users" are always on.
    enabled_modules: list[str] | None = None

    def validate_for_env(self) -> None:
        if self.env != "prod":
            return
        problems = []
        if self.jwt_secret == DEFAULT_SECRET or len(self.jwt_secret) < 32:
            problems.append("HUB_JWT_SECRET must be set to >= 32 random characters")
        if self.bootstrap_admin_password == DEFAULT_ADMIN_PASSWORD:
            problems.append("HUB_BOOTSTRAP_ADMIN_PASSWORD must not be the default")
        if problems:
            raise RuntimeError("Refusing to start in prod: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
