"""Process-wide durable store access for Reflex state handlers.

State handlers call :func:`stores` and translate failures into UI banners —
per ADR-0005 they never touch drivers or schema DDL themselves.

Driver selection (BE-1) routes through :mod:`WisPay.services.db`:

- **Azure SQL** (production): ``pyodbc`` connections forcibly close on idle
  (SQLSTATE ``08S01`` / ``10054``). The cached bundle is revalidated with a
  cheap ``SELECT 1`` on every call; a dead link is closed and replaced
  transparently.
- **SQLite** (dev / CI): a single ``sqlite3`` connection per process. WAL
  mode is enabled in :mod:`WisPay.services.db.sqlite_connect`; no
  reconnect path is needed because the local driver does not drop.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from typing import TYPE_CHECKING

from WisPay.services import db as _db
from WisPay.services.sql_repositories import sql_stores as _sql_stores  # noqa: F401
from WisPay.services.sqlite_repositories import sqlite_stores as _sqlite_stores  # noqa: F401

if TYPE_CHECKING:
    from WisPay.services.repositories import Stores

_lock = threading.Lock()
_cached: Stores | None = None
_cached_conn: object | None = None  # pyodbc.Connection | sqlite3.Connection

#: SQLSTATE prefixes that indicate a broken/transient Azure SQL link.
CONNECTION_FAILURE_PREFIXES = (
    "08S01",
    "08001",
    "08003",
    "08S02",
    "HYT00",
    "HYT01",
    "40001",
)


def is_connection_failure(error: BaseException) -> bool:
    """Return whether ``error`` is a pyodbc broken/transient link failure."""
    args = getattr(error, "args", ())
    sqlstate = str(args[0]) if args else ""
    return type(error).__module__.startswith("pyodbc") and sqlstate.startswith(
        CONNECTION_FAILURE_PREFIXES
    )


def _connection_alive(conn: object) -> bool:
    """Return whether ``conn`` can answer ``SELECT 1``.

    SQLite connections are probed with :func:`sqlite3.Connection.execute`;
    other drivers (Azure SQL via ``pyodbc``) use the cursor API. Unknown
    objects return ``False`` rather than raising so the cached-link path
    never bubbles an ``AttributeError`` to callers.
    """
    if isinstance(conn, sqlite3.Connection):
        try:
            conn.execute("SELECT 1").fetchone()
        except Exception:
            return False
        return True
    cursor = getattr(conn, "cursor", None)
    if cursor is None:
        return False
    try:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    except Exception:
        return False
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()
    return True


def stores(*, ensure_tables: bool = True) -> Stores:
    """Return a live store bundle, reconnecting when the cached link died.

    Raises ``RuntimeError`` with a setup hint when the configured driver is
    unreachable; callers own the user-facing message.
    """

    global _cached, _cached_conn
    if _cached is not None and _cached_conn is not None and _connection_alive(_cached_conn):
        return _cached
    with _lock:
        if _cached is not None and _cached_conn is not None and _connection_alive(_cached_conn):
            return _cached
        if _cached_conn is not None:
            with contextlib.suppress(Exception):
                _cached_conn.close()  # type: ignore[attr-defined]  # sqlite3 or pyodbc
        kind = _db.driver_kind()
        if kind == "sqlite":
            # Use the module-level symbol so tests can monkeypatch it.
            _cached = _sqlite_stores(ensure_tables=ensure_tables)
            _cached_conn = _db.sqlite_connect()
        else:
            # Use the module-level symbol so tests can monkeypatch it.
            conn = _db.azure_connect()
            _cached = _sql_stores(conn, ensure_tables=ensure_tables)
            _cached_conn = conn
    return _cached


def reset_stores() -> None:
    """Drop the cached bundle (used by tests and after connection loss)."""

    global _cached, _cached_conn
    with _lock:
        if _cached_conn is not None:
            with contextlib.suppress(Exception):
                _cached_conn.close()  # type: ignore[attr-defined]
        _cached = None
        _cached_conn = None
