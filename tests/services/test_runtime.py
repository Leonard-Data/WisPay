"""Tests for the revalidating store runtime (dual-driver BE-1)."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pyodbc
import pytest

from WisPay.services import db, runtime


@pytest.fixture(autouse=True)
def _isolated_cache() -> None:
    runtime.reset_stores()
    yield
    runtime.reset_stores()


def test_connection_failure_classifier() -> None:
    dead = pyodbc.OperationalError("08S01", "Communication link failure", 10054)
    assert runtime.is_connection_failure(dead)
    transient = pyodbc.OperationalError("40001", "deadlock victim", 0)
    assert runtime.is_connection_failure(transient)
    plain = ValueError("nope")
    assert not runtime.is_connection_failure(plain)
    wrong_state = pyodbc.IntegrityError("23000", "duplicate key", 0)
    assert not runtime.is_connection_failure(wrong_state)


def test_sqlite_connection_alive_round_trip() -> None:
    """The reconnect probe works on ``sqlite3`` too (used by dev)."""
    conn = db.sqlite_connect_in_memory()
    try:
        assert runtime._connection_alive(conn) is True
    finally:
        conn.close()
    # Non-Connection objects fail fast.
    assert runtime._connection_alive(object()) is False


def test_stores_reconnects_when_cached_link_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Azure SQL path: a dead cached link triggers a fresh connect + bundle."""
    first_bundle = SimpleNamespace(name="first")
    second_bundle = SimpleNamespace(name="second")
    first_conn = SimpleNamespace(closed=False)
    second_conn = SimpleNamespace(closed=False)
    connect_calls: list[int] = []

    def fake_azure_connect() -> object:
        index = len(connect_calls)
        connect_calls.append(index)
        return first_conn if index == 0 else second_conn

    alive_results = iter([False, False])

    def fake_alive(_conn: object) -> bool:
        return next(alive_results)

    monkeypatch.setattr(db, "driver_kind", lambda: "azure-sql")
    monkeypatch.setattr(db, "azure_connect", fake_azure_connect)
    monkeypatch.setattr(runtime, "_connection_alive", fake_alive)
    # runtime._sql_stores is the module-level reference used by runtime.stores().
    monkeypatch.setattr(
        runtime,
        "_sql_stores",
        lambda conn, *, ensure_tables: first_bundle if conn is first_conn else second_bundle,
    )

    assert runtime.stores() is first_bundle
    # Cached link died -> new connection, new bundle.
    assert runtime.stores(ensure_tables=False) is second_bundle
    assert len(connect_calls) == 2


def test_stores_uses_sqlite_path_when_url_is_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite path: ``WS_DB_URL=sqlite://...`` opens an in-memory file."""
    original_connect = db.sqlite_connect

    def in_memory_connect(url: str | None = None) -> sqlite3.Connection:
        # Bypass the patched function below by calling the original with a
        # fresh in-memory URL.
        return original_connect("sqlite:///:memory:")

    monkeypatch.setattr(db, "driver_kind", lambda: "sqlite")
    monkeypatch.setattr(db, "sqlite_connect", in_memory_connect)
    # Stub _sqlite_stores so it builds stores from the in-memory connection
    # we just configured instead of opening a fresh one via the runtime cache.
    from WisPay.services.sqlite_repositories import sqlite_stores as real_sqlite_stores

    monkeypatch.setattr(
        runtime,
        "_sqlite_stores",
        lambda *, ensure_tables: real_sqlite_stores(
            ensure_tables=ensure_tables, conn=original_connect("sqlite:///:memory:")
        ),
    )

    bundle = runtime.stores()
    assert isinstance(runtime._cached_conn, sqlite3.Connection)
    from WisPay.services.repositories import (
        AuditEventStore,
        RequestStore,
        RuleStore,
        WorkflowStore,
    )

    assert isinstance(bundle.requests, RequestStore)
    assert isinstance(bundle.workflows, WorkflowStore)
    assert isinstance(bundle.audit, AuditEventStore)
    assert isinstance(bundle.rules, RuleStore)
