"""Requests list state adapter.

Search / filter / saved-view persistence for the ``/requests`` page. Reads
through the ``Stores`` Protocol only (ADR-0005); never imports a driver.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.services.reference_data import REQUESTER_PROTOTYPE
from WisPay.services.request_query import QueueQuery, format_money, queue_rows
from WisPay.services.runtime import stores

if TYPE_CHECKING:
    from WisPay.models import PaymentRequest


def _rows_for(
    models: tuple[PaymentRequest, ...],
    query: QueueQuery,
) -> list[dict[str, str]]:
    today = date(2026, 8, 24)
    projected = queue_rows(models, viewer=REQUESTER_PROTOTYPE, today=today, query=query)
    return [
        {
            "request_id": str(row.request_id),
            "number": row.number,
            "payee": row.payee_display,
            "type_icon": row.type_label[:1].upper(),
            "family_subtype": row.type_label,
            "amount_display": format_money(row.amount),
            "state": row.state.value,
            "tone": "info",
            "overdue": "",
            "submitted_display": row.submitted_at.strftime("%d %b %Y") if row.submitted_at else "",
        }
        for row in projected
    ]


class RequestsState(rx.State):
    """Search, filter, and saved-view state for ``/requests``."""

    rows: list[dict[str, str]] = []
    search_text: str = ""
    status_filter: str = ""
    family_filter: str = ""
    cost_center_filter: str = ""
    saved_view: str = "all"
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild the queue projection off the event loop."""

        def _compute() -> tuple[list[dict[str, str]], str]:
            try:
                bundle = stores()
            except RuntimeError as exc:
                return [], str(exc)
            models = bundle.requests.list_all()
            query = QueueQuery(
                search_text=self.search_text,
                status=self.status_filter,
                family=self.family_filter,
                cost_center=self.cost_center_filter,
            )
            return _rows_for(models, query), ""

        rows, error = await run_in_threadpool(_compute)
        self.rows = rows
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh the queue projection."""

        await self._refresh()

    @rx.event
    async def set_search(self, value: str) -> None:
        """Store the search text and re-project."""

        self.search_text = value
        await self._refresh()

    @rx.event
    async def set_status(self, value: str) -> None:
        """Store the status filter and re-project."""

        self.status_filter = value
        await self._refresh()

    @rx.event
    async def set_family(self, value: str) -> None:
        """Store the family filter and re-project."""

        self.family_filter = value
        await self._refresh()

    @rx.event
    async def set_saved_view(self, value: str) -> None:
        """Store the saved view selection and re-project."""

        self.saved_view = value
        await self._refresh()

    @rx.event
    async def clear_filters(self) -> None:
        """Reset every filter back to the default view."""

        self.search_text = ""
        self.status_filter = ""
        self.family_filter = ""
        self.cost_center_filter = ""
        self.saved_view = "all"
        await self._refresh()


__all__ = ["RequestsState"]
