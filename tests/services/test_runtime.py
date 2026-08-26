"""Tests for the revalidating store runtime."""

from __future__ import annotations

from types import SimpleNamespace

import pyodbc
import pytest

from WisPay.services import runtime


@pytest.fixture(autouse=True)
def _isolated_cache():
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


def test_stores_reconnects_when_cached_link_dies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_bundle = SimpleNamespace(name="first")
    second_bundle = SimpleNamespace(name="second")
    first_conn = SimpleNamespace(closed=False)
    second_conn = SimpleNamespace(closed=False)
    connect_calls: list[int] = []

    def fake_connect():
        index = len(connect_calls)
        connect_calls.append(index)
        return first_conn if index == 0 else second_conn

    monkeypatch.setattr(runtime, "connect", fake_connect)
    monkeypatch.setattr(
        runtime,
        "sql_stores",
        lambda conn, *, ensure_tables: first_bundle if conn is first_conn else second_bundle,
    )
    monkeypatch.setattr(
        runtime,
        "_connection_alive",
        lambda conn: next(alive_results),
    )
    alive_results = iter([False, False])

    assert runtime.stores() is first_bundle
    # Cached link died -> new connection, new bundle.
    assert runtime.stores(ensure_tables=False) is second_bundle
    assert len(connect_calls) == 2
