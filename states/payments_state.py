"""Payments state adapter (Start / Record / Close operators).

Reads Approved / Payment in Process / Paid / Closure Due queues from the
durable stores; never imports a driver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.models import LifecycleState
from WisPay.services.request_query import format_money
from WisPay.services.runtime import stores

if TYPE_CHECKING:
    from WisPay.models import PaymentRequest


def _payment_rows(
    models: tuple[PaymentRequest, ...],
    target: LifecycleState,
    *,
    stage: str,
) -> list[dict[str, str]]:
    return [
        {
            "number": req.request_number or "—",
            "payee": req.beneficiary.display_name,
            "subtype": req.request_type.value,
            "amount_display": format_money(req.total_amount),
            "stage": stage,
            "stage_label": target.value,
        }
        for req in models
        if req.lifecycle_state is target
    ]


class PaymentsState(rx.State):
    """Operator queue for the payment recording page."""

    approved_rows: list[dict[str, str]] = []
    in_process_rows: list[dict[str, str]] = []
    paid_rows: list[dict[str, str]] = []
    closure_due_rows: list[dict[str, str]] = []
    status_message: str = ""
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild the operator queue off the event loop."""

        def _compute() -> tuple[
            list[dict[str, str]],
            list[dict[str, str]],
            list[dict[str, str]],
            list[dict[str, str]],
            str,
        ]:
            try:
                bundle = stores()
            except RuntimeError as exc:
                return [], [], [], [], str(exc)
            models = bundle.requests.list_all()
            return (
                _payment_rows(models, LifecycleState.APPROVED, stage="approved"),
                _payment_rows(models, LifecycleState.PAYMENT_IN_PROCESS, stage="in_process"),
                _payment_rows(models, LifecycleState.PAID, stage="paid"),
                _payment_rows(models, LifecycleState.PAID, stage="closure_due"),
                "",
            )

        approved, in_process, paid, closure_due, error = await run_in_threadpool(_compute)
        self.approved_rows = approved
        self.in_process_rows = in_process
        self.paid_rows = paid
        self.closure_due_rows = closure_due
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh the operator queue."""

        await self._refresh()

    @rx.event
    async def start(self, number: str) -> None:
        """Move an Approved request to Payment in Process (t5 demo flow)."""

        self.status_message = f"Start requested for {number} — wire to service in t6."

    @rx.event
    async def record(self, number: str) -> None:
        """Record the external reference for a Payment-in-Process request."""

        self.status_message = f"Record requested for {number} — wire to service in t6."

    @rx.event
    async def close(self, number: str) -> None:
        """Mark a Paid request Closed (read-only banner afterwards)."""

        self.status_message = f"Close requested for {number} — wire to service in t6."


__all__ = ["PaymentsState"]
