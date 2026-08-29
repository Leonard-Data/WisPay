"""Tests for Azure SQL connection assembly and managed schema statements."""

from __future__ import annotations

from pathlib import Path

import pytest

from WisPay.services import db

_REQUIRED = ("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE", "AZURE_SQL_USERNAME")


def _clear_sql_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        *_REQUIRED,
        "AZURE_SQL_PASSWORD",
        "AZURE_SQL_DRIVER",
        "AZURE_SQL_ENCRYPT",
        "AZURE_SQL_TRUST_SERVER_CERTIFICATE",
        # The dual-driver selector lives in WS_DB_URL — clear it so the
        # Azure SQL tests in this module reach the Azure path.
        "WS_DB_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_missing_env_vars_raise_readable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_sql_env(monkeypatch)
    with pytest.raises(RuntimeError, match="AZURE_SQL_SERVER.*AZURE_SQL_DATABASE"):
        db.connection_string()


def test_connection_string_assembles_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_sql_env(monkeypatch)
    monkeypatch.setenv("AZURE_SQL_SERVER", "tcp:sql.example.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "db-wispay-test")
    monkeypatch.setenv("AZURE_SQL_USERNAME", "wispay-app")
    monkeypatch.setenv("AZURE_SQL_PASSWORD", "secret")
    result = db.connection_string()
    assert result.startswith("Driver={ODBC Driver 18 for SQL Server};")
    assert "Server=tcp:sql.example.database.windows.net,1433;" in result
    assert "Database=db-wispay-test;" in result
    assert "Uid=wispay-app;" in result
    assert "Pwd=secret;" in result
    assert "Encrypt=yes;" in result
    assert "TrustServerCertificate=no;" in result


def test_connection_string_honors_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_sql_env(monkeypatch)
    monkeypatch.setenv("AZURE_SQL_SERVER", "sql.example.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "db")
    monkeypatch.setenv("AZURE_SQL_USERNAME", "u")
    monkeypatch.setenv("AZURE_SQL_PASSWORD", "p")
    monkeypatch.setenv("AZURE_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    monkeypatch.setenv("AZURE_SQL_ENCRYPT", "no")
    monkeypatch.setenv("AZURE_SQL_TRUST_SERVER_CERTIFICATE", "yes")
    result = db.connection_string()
    assert result.startswith("Driver={ODBC Driver 17 for SQL Server};")
    assert "Encrypt=no;" in result
    assert "TrustServerCertificate=yes;" in result


def test_connect_wraps_failures_with_setup_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_sql_env(monkeypatch)
    monkeypatch.setenv("AZURE_SQL_SERVER", "sql.example.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "db")
    monkeypatch.setenv("AZURE_SQL_USERNAME", "u")
    monkeypatch.setenv("AZURE_SQL_PASSWORD", "p")

    import pyodbc

    def _explode(*args: object, **kwargs: object) -> object:
        raise OSError("login timeout")

    monkeypatch.setattr(pyodbc, "connect", _explode)
    with pytest.raises(RuntimeError, match="firewall") as excinfo:
        db.connect()
    assert isinstance(excinfo.value.__cause__, OSError)


def _normalized(sql: str) -> str:
    return " ".join(sql.split())


def test_schema_statements_are_individually_guarded() -> None:
    expected_tables = (
        "dbo.wispay_payment_request",
        "dbo.wispay_workflow_instance",
        "dbo.wispay_workflow_rule",
        "dbo.wispay_workflow_rule_version",
        "dbo.wispay_audit_event",
        "dbo.wispay_payment_record",
    )
    joined = "\n".join(statement.lower() for statement in db.schema_statements())
    for table in expected_tables:
        assert f"if object_id(n'{table}', n'u') is null" in joined, table
        assert f"create table {table}" in joined, table


def test_schema_sql_file_mirrors_managed_statements() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "scripts" / "sql" / "schema.sql"
    raw = schema_path.read_text(encoding="utf-8")
    body = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("--"))
    file_statements = {_normalized(part) for part in body.split(";") if _normalized(part)}
    managed = {_normalized(s) for s in db.schema_statements()}
    assert file_statements == managed
