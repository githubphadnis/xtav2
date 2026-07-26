"""Runtime app settings (UI overrides on top of env defaults)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSetting

PRIVACY_KEY = "privacy_local_only"


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row else None


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def privacy_local_only(db: Session, settings: Settings) -> bool:
    """Effective privacy: DB override if set, else env PRIVACY_LOCAL_ONLY."""
    raw = get_setting(db, PRIVACY_KEY)
    if raw is None:
        return settings.privacy_local_only
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def set_privacy_local_only(db: Session, enabled: bool) -> None:
    set_setting(db, PRIVACY_KEY, "true" if enabled else "false")


def google_vision_allowed(db: Session, settings: Settings) -> bool:
    """Cloud Vision only when privacy permits and flag + key are set."""
    return (
        not privacy_local_only(db, settings)
        and settings.feature_ocr_google_vision
        and bool(settings.google_vision_api_key.strip())
    )
