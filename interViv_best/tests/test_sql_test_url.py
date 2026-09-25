"""The opt-in Postgres URL must not be able to name a real database."""

from __future__ import annotations

import pytest

from tests.sql_test_url import resolve_sql_url


def test_guard_rejects_non_test_url(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "INTERVIV_TEST_DATABASE_URL",
        "postgresql+psycopg://interviv:secret@db.example.com:5432/interviv",
    )
    with pytest.raises(RuntimeError, match="drop the public schema"):
        resolve_sql_url(tmp_path, "followup.db")

    monkeypatch.setenv(
        "INTERVIV_TEST_DATABASE_URL",
        "postgresql+psycopg://interviv@127.0.0.1:5432/interviv",
    )
    with pytest.raises(RuntimeError, match="drop the public schema"):
        resolve_sql_url(tmp_path, "followup.db")
