"""Database URL normalization tests."""

from app.db import normalize_database_url


def test_normalize_database_url_psycopg3() -> None:
    assert (
        normalize_database_url("postgresql://xtav2:secret@postgres:5432/xtav2")
        == "postgresql+psycopg://xtav2:secret@postgres:5432/xtav2"
    )


def test_normalize_database_url_already_psycopg() -> None:
    url = "postgresql+psycopg://xtav2:secret@postgres:5432/xtav2"
    assert normalize_database_url(url) == url


def test_normalize_sqlite_unchanged() -> None:
    url = "sqlite+pysqlite:///:memory:"
    assert normalize_database_url(url) == url
