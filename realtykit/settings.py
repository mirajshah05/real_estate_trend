"""Environment-only settings. No secrets in source."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", validation_alias="REALTYKIT_HOST")
    port: int = Field(default=8770, validation_alias="REALTYKIT_PORT")
    data_dir: Path | None = Field(default=None, validation_alias="REALTYKIT_DATA_DIR")
    resources_dir: Path | None = Field(default=None, validation_alias="REALTYKIT_RESOURCES_DIR")
    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        validation_alias="REALTYKIT_CORS_ORIGINS",
    )
    fred_api_key: str | None = Field(default=None, validation_alias="FRED_API_KEY")
    rentcast_api_key: str | None = Field(default=None, validation_alias="RENTCAST_API_KEY")
    attom_api_key: str | None = Field(default=None, validation_alias="ATTOM_API_KEY")
    rentcast_monthly_limit: int = Field(default=40, validation_alias="RENTCAST_MONTHLY_LIMIT")
    rentcast_warning_at: int = Field(default=32, validation_alias="RENTCAST_WARNING_AT")
    user_agent: str = Field(
        default="RealtyKit/0.1 (local housing dashboard)",
        validation_alias="REALTYKIT_USER_AGENT",
    )

    @property
    def root(self) -> Path:
        return _REPO_ROOT

    @property
    def data(self) -> Path:
        path = self.data_dir if self.data_dir else _REPO_ROOT / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def raw_dir(self) -> Path:
        path = self.data / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resources(self) -> Path:
        path = self.resources_dir if self.resources_dir else _REPO_ROOT / "resources"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def government_snapshot_dir(self) -> Path:
        snapshot_date = datetime.now(UTC).date().isoformat()
        path = self.resources / "government" / snapshot_date
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def fixtures_dir(self) -> Path:
        return self.data / "fixtures"

    @property
    def db_path(self) -> Path:
        return self.data / "realtykit.db"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_fred_key(self) -> bool:
        return bool(self.fred_api_key)

    @property
    def has_rentcast_key(self) -> bool:
        return bool(self.rentcast_api_key)

    @property
    def has_attom_key(self) -> bool:
        return bool(self.attom_api_key)


def get_settings() -> Settings:
    return Settings()
