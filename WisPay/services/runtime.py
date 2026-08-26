"""Process-wide durable store access for Reflex state handlers.

State handlers call :func:`stores` and translate failures into UI banners —
per ADR-0005 they never touch drivers or schema DDL themselves.

Azure SQL (and intermediate firewalls) forcibly close idle connections
(``08S01``/``10054``). The cached bundle is therefore revalidated with a cheap
``SELECT 1`` on every call; a dead link is closed and replaced transparently.
"""

from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING

from WisPay.services.db import connect
from WisPay.services.sql_repositories import sql_stores

if TYPE_CHECKING:
    import pyodbc

    from WisPay.services.repositories import Stores

_lock = threading.Lock()
_cached: Stores | None = None
_cached_conn: pyodbc.Connection | None = None

#: SQLSTATE prefixes that indicate a broken/transient link worth reconnecting.
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


def _connection_alive(conn: pyodbc.Connection) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    except Exception:
        return False
    finally:
        cursor.close()
    return True


def stores(*, ensure_tables: bool = True) -> Stores:
    """Return a live store bundle, reconnecting when the cached link died.

    Raises ``RuntimeError`` with a setup hint when Azure SQL is unreachable;
    callers own the user-facing message.
    """

    global _cached, _cached_conn
    if _cached is not None and _cached_conn is not None and _connection_alive(_cached_conn):
        return _cached
    with _lock:
        if _cached is not None and _cached_conn is not None and _connection_alive(_cached_conn):
            return _cached
        if _cached_conn is not None:
            with contextlib.suppress(Exception):
                _cached_conn.close()
        conn = connect()
        _cached = sql_stores(conn, ensure_tables=ensure_tables)
        _cached_conn = conn
    return _cached


def reset_stores() -> None:
    """Drop the cached bundle (used by tests and after connection loss)."""

    global _cached, _cached_conn
    with _lock:
        if _cached_conn is not None:
            with contextlib.suppress(Exception):
                _cached_conn.close()
        _cached = None
        _cached_conn = None
