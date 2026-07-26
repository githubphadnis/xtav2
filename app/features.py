"""Feature-flag helpers — single place to gate modules."""

from __future__ import annotations

from app.config import Settings, get_settings


def flag_snapshot(settings: Settings | None = None) -> dict[str, bool]:
    """Return all FEATURE_* flags for health / MCP introspection."""
    s = settings or get_settings()
    return {
        "FEATURE_MANUAL_ENTRY": s.feature_manual_entry,
        "FEATURE_MULTI_CURRENCY": s.feature_multi_currency,
        "FEATURE_OLLAMA_QA": s.feature_ollama_qa,
        "FEATURE_MCP": s.feature_mcp,
        "FEATURE_RECEIPT_OCR": s.feature_receipt_ocr,
        "FEATURE_MASS_UPLOAD": s.feature_mass_upload,
        "FEATURE_OCR_OLLAMA_VISION": s.feature_ocr_ollama_vision,
        "FEATURE_OCR_GOOGLE_VISION": s.feature_ocr_google_vision,
        "FEATURE_BANK_IMPORT": s.feature_bank_import,
        "FEATURE_EMAIL_INGEST": s.feature_email_ingest,
        "FEATURE_LINE_ITEMS": s.feature_line_items,
        "FEATURE_SAVINGS_INSIGHTS": s.feature_savings_insights,
        "FEATURE_TRENDS_UI": s.feature_trends_ui,
        "FEATURE_GEO": s.feature_geo,
    }


def require_flag(name: str, settings: Settings | None = None) -> bool:
    """Return whether a named flag is enabled."""
    return bool(flag_snapshot(settings).get(name, False))
