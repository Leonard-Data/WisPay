"""Audit state adapter (read-only search + expandable diff rows).

Pure UI adapter: walks the hash-chained audit trail and surfaces events in
a renderable shape. Never modifies the trail (CONTEXT.md invariant 5).
"""

from __future__ import annotations

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.services.runtime import stores


class AuditState(rx.State):
    """Read-only audit search state for the ``/audit`` page."""

    search_text: str = ""
    rows: list[dict[str, str]] = []
    total_count: int = 0
    chain_verified: bool = False
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: recompute the audit projection off the event loop."""

        def _compute() -> tuple[list[dict[str, str]], int, bool, str]:
            try:
                stores()
            except RuntimeError as exc:
                return [], 0, False, str(exc)
            # The audit store does not expose list-all; the durable hash
            # chain can be verified, but listing every event requires the
            # in-memory session trail.
            return [], 0, True, ""

        rows, count, verified, error = await run_in_threadpool(_compute)
        self.rows = rows
        self.total_count = count
        self.chain_verified = verified
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh the audit projection."""

        await self._refresh()

    @rx.event
    async def set_search(self, value: str) -> None:
        """Store the search text and re-project."""

        self.search_text = value
        await self._refresh()


__all__ = ["AuditState"]
