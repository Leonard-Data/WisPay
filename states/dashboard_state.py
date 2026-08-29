"""Dashboard state adapter (persona-aware widgets).

Reads seed/durable data through the ``Stores`` Protocol only; never touches
the driver directly (ADR-0005 seam).
"""

from __future__ import annotations

from datetime import date

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.services.reference_data import REQUESTER_PROTOTYPE
from WisPay.services.request_query import QueueQuery, RequestQueueRow, queue_rows
from WisPay.services.runtime import stores


def _state_counts(rows: tuple[RequestQueueRow, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.state.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _activity_rows(rows: tuple[RequestQueueRow, ...]) -> list[dict[str, str]]:
    return [
        {
            "when": row.submitted_at.strftime("%d %b %Y") if row.submitted_at else "",
            "action": row.state.value,
            "subject": row.number,
            "actor": "system",
        }
        for row in rows[:5]
    ]


class DashboardState(rx.State):
    """Persona-aware KPI tiles + activity feed for the dashboard."""

    kpi_counts: dict[str, int] = {}
    activity_rows: list[dict[str, str]] = []
    persona_label: str = REQUESTER_PROTOTYPE.display_name
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild dashboard projections off the event loop."""

        def _compute() -> tuple[dict[str, int], list[dict[str, str]], str]:
            try:
                bundle = stores()
            except RuntimeError as exc:
                return {}, [], str(exc)
            models = bundle.requests.list_all()
            today = date(2026, 8, 24)  # demo reference date (BS-1 §4.1)
            rows = queue_rows(
                models,
                viewer=REQUESTER_PROTOTYPE,
                today=today,
                query=QueueQuery(),
            )
            return _state_counts(rows), _activity_rows(rows), ""

        counts, activity, error = await run_in_threadpool(_compute)
        self.kpi_counts = counts
        self.activity_rows = activity
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh dashboard projections."""

        await self._refresh()


__all__ = ["DashboardState"]
