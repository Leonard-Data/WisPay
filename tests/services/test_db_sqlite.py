"""Tests for the SQLite driver side of :mod:`WisPay.services.db`.

Exercises URL resolution, default fallback, schema bootstrap, and the
``ensure_schema`` dispatcher. No Azure env vars are required.
"""

from __future__ import annotations

import pytest

from WisPay.services import db


def _clear_azure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AZURE_SQL_SERVER",
        "AZURE_SQL_DATABASE",
        "AZURE_SQL_USERNAME",
        "AZURE_SQL_PASSWORD",
        "AZURE_SQL_DRIVER",
        "AZURE_SQL_ENCRYPT",
        "AZURE_SQL_TRUST_SERVER_CERTIFICATE",
        "WS_DB_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_driver_kind_defaults_to_sqlite_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_azure_env(monkeypatch)
    assert db.driver_kind() == "sqlite"
    assert db.default_db_url() == db.DEFAULT_SQLITE_URL


def test_driver_kind_uses_ws_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_azure_env(monkeypatch)
    monkeypatch.setenv("WS_DB_URL", "sqlite:///custom.db")
    assert db.driver_kind() == "sqlite"
    assert db.default_db_url() == "sqlite:///custom.db"


def test_driver_kind_detects_azure_when_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_azure_env(monkeypatch)
    monkeypatch.setenv("AZURE_SQL_SERVER", "tcp:sql.example.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "db-wispay")
    monkeypatch.setenv("AZURE_SQL_USERNAME", "u")
    monkeypatch.setenv("AZURE_SQL_PASSWORD", "p")
    assert db.driver_kind() == "azure-sql"


def test_ws_db_url_wins_over_azure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_azure_env(monkeypatch)
    monkeypatch.setenv("AZURE_SQL_SERVER", "tcp:sql.example.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "db-wispay")
    monkeypatch.setenv("WS_DB_URL", "sqlite:///override.db")
    assert db.driver_kind() == "sqlite"
    assert db.default_db_url() == "sqlite:///override.db"


def test_sqlite_connect_in_memory() -> None:
    conn = db.sqlite_connect_in_memory()
    try:
        assert conn.execute("SELECT 1").fetchone() == (1,)
    finally:
        conn.close()


def test_sqlite_connect_file(tmp_path) -> None:
    target = tmp_path / "wispay.db"
    conn = db.sqlite_connect(f"sqlite:///{target}")
    try:
        conn.execute("CREATE TABLE t(x INTEGER)")
        conn.commit()
        # File exists on disk.
        assert target.exists()
    finally:
        conn.close()


def test_ensure_schema_dispatches_to_sqlite() -> None:
    conn = db.sqlite_connect("sqlite:///:memory:")
    try:
        db.ensure_schema(conn)
        # Tables present.
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in (
            "wispay_payment_request",
            "wispay_workflow_instance",
            "wispay_workflow_rule",
            "wispay_workflow_rule_version",
            "wispay_audit_event",
            "wispay_payment_record",
        ):
            assert table in names
    finally:
        conn.close()


def test_sqlite_connect_rejects_non_sqlite_url() -> None:
    with pytest.raises(ValueError, match="sqlite://"):
        db.sqlite_connect("mssql+pyodbc://nope")
