"""Application settings, loaded from environment variables (prefix ``RECON_``) or a ``.env`` file."""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RECON_", extra="ignore")

    app_name: str = "Banking Transaction Reconciliation API"
    environment: str = "development"

    # SQL Server example:
    # mssql+pyodbc://user:password@host:1433/BankRecon?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
    database_url: str = "sqlite:///./reconciliation.db"
    sql_echo: bool = False

    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_hash_iterations: int = 390_000

    # Optional bootstrap admin, created on startup when no users exist yet.
    admin_username: str | None = None
    admin_password: str | None = None

    max_upload_size_mb: int = 10

    # Default reconciliation tolerances (can be overridden per run).
    amount_tolerance: Decimal = Decimal("0.00")
    date_tolerance_days: int = 0

    log_level: str = "INFO"
    log_json: bool = False

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
