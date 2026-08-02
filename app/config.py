"""Application configuration from environment."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    """Runtime settings — no secrets or hosts hardcoded in code paths."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_log_level: str = "INFO"
    app_timezone: str = "Europe/Amsterdam"
    base_currency: str = "EUR"
    # Frankfurter (ECB) — no API key. Override if you self-host a mirror.
    fx_api_base_url: str = "https://api.frankfurter.app"

    database_url: str = "postgresql://xtav2:xtav2@postgres:5432/xtav2"

    ollama_base_url: str = "http://lenai:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_vision_model: str = ""
    ollama_timeout_seconds: int = 60
    ollama_vision_timeout_seconds: int = 120

    # When true, never send receipt images/text to cloud OCR (blocks Google Vision).
    privacy_local_only: bool = True
    google_vision_api_key: str = ""

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    # Operator wipe+reimport (#24). Empty = LAN private-IP + confirm body only.
    ops_reimport_token: str = ""

    feature_manual_entry: bool = True
    feature_multi_currency: bool = True
    feature_ollama_qa: bool = True
    feature_mcp: bool = True
    feature_receipt_ocr: bool = False
    feature_mass_upload: bool = False
    feature_mass_rename: bool = True
    feature_ocr_ollama_vision: bool = False
    feature_ocr_google_vision: bool = False
    feature_bank_import: bool = False
    feature_email_ingest: bool = False
    feature_line_items: bool = True
    feature_savings_insights: bool = False
    feature_trends_ui: bool = False
    feature_geo: bool = False

    @field_validator(
        "privacy_local_only",
        "feature_manual_entry",
        "feature_multi_currency",
        "feature_ollama_qa",
        "feature_mcp",
        "feature_receipt_ocr",
        "feature_mass_upload",
        "feature_mass_rename",
        "feature_ocr_ollama_vision",
        "feature_ocr_google_vision",
        "feature_bank_import",
        "feature_email_ingest",
        "feature_line_items",
        "feature_savings_insights",
        "feature_trends_ui",
        "feature_geo",
        mode="before",
    )
    @classmethod
    def parse_bool_flags(cls, value: object) -> bool:
        return _as_bool(value)

    def ollama_vision_allowed(self) -> bool:
        return self.feature_ocr_ollama_vision and bool(self.ollama_vision_model.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
