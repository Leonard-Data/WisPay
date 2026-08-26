"""Process-wide durable store access for Reflex state handlers.

State handlers call :func:`stores` and translate failures into UI banners —
per ADR-0005 they never touch drivers or schema DDL themselves.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from WisPay.services.db import connect
from WisPay.services.sql_repositories import sql_stores

if TYPE_CHECKING:
    from WisPay.services.repositories import Stores

_lock = threading.Lock()
_cached: Stores | None = None


def stores(*, ensure_tables: bool = True) -> Stores:
    """Return the cached store bundle, connecting and bootstrapping once.

    Raises ``RuntimeError`` with a setup hint when Azure SQL is unreachable;
    callers own the user-facing message.
    """

    global _cached
    if _cached is not None:
        return _cached
    with _lock:
        if _cached is None:
            _cached = sql_stores(connect(), ensure_tables=ensure_tables)
    return _cached


def reset_stores() -> None:
    """Drop the cached bundle (used by tests and after connection loss)."""

    global _cached
    with _lock:
        _cached = None
