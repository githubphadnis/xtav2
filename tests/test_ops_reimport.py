"""Tests for LAN operator reimport endpoint."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["FEATURE_RECEIPT_OCR"] = "true"
os.environ["FEATURE_OCR_GOOGLE_VISION"] = "false"
os.environ["PRIVACY_LOCAL_ONLY"] = "true"

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import init_db
from app.main import app

_tmp_upload: tempfile.TemporaryDirectory[str] | None = None


def setup_function() -> None:
    global _tmp_upload
    if _tmp_upload is not None:
        _tmp_upload.cleanup()
    _tmp_upload = tempfile.TemporaryDirectory(prefix="xtav2-ops-")
    os.environ["UPLOAD_DIR"] = _tmp_upload.name
    os.environ["OPS_REIMPORT_TOKEN"] = "test-ops-token"
    get_settings.cache_clear()
    from app import db as db_mod

    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    init_db()
    (Path(_tmp_upload.name) / "r.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 8)


def teardown_function() -> None:
    global _tmp_upload
    if _tmp_upload is not None:
        _tmp_upload.cleanup()
        _tmp_upload = None


def test_ops_reimport_dry_run() -> None:
    client = TestClient(app)
    response = client.post(
        "/ops/reimport",
        json={"confirm": "WIPE_AND_REIMPORT", "dry_run": True},
        headers={"Authorization": "Bearer test-ops-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["files_found"] == 1
    assert data["enqueued"] == 0


def test_ops_reimport_rejects_bad_confirm() -> None:
    client = TestClient(app)
    response = client.post(
        "/ops/reimport",
        json={"confirm": "nope"},
        headers={"Authorization": "Bearer test-ops-token"},
    )
    assert response.status_code == 400


def test_ops_reimport_rejects_bad_token() -> None:
    client = TestClient(app)
    response = client.post(
        "/ops/reimport",
        json={"confirm": "WIPE_AND_REIMPORT", "dry_run": True},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
