from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "万州商户通 API"
    environment: str = "development"
    database_url: str = "sqlite:///./wanzhou.db"
    mysql_database: str | None = None
    mysql_user: str | None = None
    mysql_password: str | None = None
    mysql_host: str = "db"
    mysql_port: int = 3306
    jwt_secret: str
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    login_attempts_per_minute: int = 8
    demo_operator_password: str
    demo_merchant_password: str
    upload_dir: str = "uploads"
    credential_encryption_key: str
    credential_encryption_previous_keys: str = ""
    backup_dir: str = "/backups"
    backup_status_file: str = "/status/latest.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() != "production":
            return self

        errors: list[str] = []
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be a unique value of at least 32 characters")
        if len(self.credential_encryption_key) < 32:
            errors.append(
                "CREDENTIAL_ENCRYPTION_KEY must be a unique value of at least 32 characters"
            )
        previous_credential_keys = [
            item.strip()
            for item in self.credential_encryption_previous_keys.split(",")
            if item.strip()
        ]
        if any(len(item) < 32 for item in previous_credential_keys):
            errors.append(
                "all CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS values must be at least 32 characters"
            )
        if self.credential_encryption_key in previous_credential_keys:
            errors.append("the current credential encryption key must not be repeated")
        if self.jwt_secret == self.credential_encryption_key:
            errors.append("JWT_SECRET and CREDENTIAL_ENCRYPTION_KEY must be different")
        if not self.mysql_database or not self.mysql_user or not self.mysql_password:
            errors.append("production must use an explicitly configured MySQL database")
        if "*" in self.allowed_origins:
            errors.append("CORS_ORIGINS must not contain a wildcard in production")
        if not self.allowed_origins or any(
            not origin.startswith("https://") for origin in self.allowed_origins
        ):
            errors.append("all production CORS_ORIGINS must use HTTPS")
        if len(self.demo_operator_password) < 12:
            errors.append("DEMO_OPERATOR_PASSWORD must contain at least 12 characters")
        if len(self.demo_merchant_password) < 12:
            errors.append("DEMO_MERCHANT_PASSWORD must contain at least 12 characters")
        if self.demo_operator_password == self.demo_merchant_password:
            errors.append("demo operator and merchant passwords must be different")
        if errors:
            raise ValueError("unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
