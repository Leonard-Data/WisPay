"""Finance Review state adapter (Budget / Compliance / Evidence / Approval).

Pure UI adapter per ADR-0005: reads the durable stores through the Protocol
only and translates the lifecycle state into the four review buckets.
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


def _bucket_rows(
    models: tuple[PaymentRequest, ...],
    target: LifecycleState,
) -> list[dict[str, str]]:
    return [
        {
            "number": req.request_number or "—",
            "payee": req.beneficiary.display_name,
            "subtype": req.request_type.value,
            "amount_display": format_money(req.total_amount),
            "stage_label": req.lifecycle_state.value,
        }
        for req in models
        if req.lifecycle_state is target
    ]


class FinanceReviewState(rx.State):
    """Queue state for the four review buckets on ``/finance-review``."""

    budget_rows: list[dict[str, str]] = []
    compliance_rows: list[dict[str, str]] = []
    evidence_rows: list[dict[str, str]] = []
    approval_rows: list[dict[str, str]] = []
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild every review bucket off the event loop."""

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
                _bucket_rows(models, LifecycleState.BUDGET_REVIEW),
                _bucket_rows(models, LifecycleState.COMPLIANCE_REVIEW),
                _bucket_rows(models, LifecycleState.EVIDENCE_VALIDATION),
                _bucket_rows(models, LifecycleState.APPROVAL_PENDING),
                "",
            )

        budget, compliance, evidence, approval, error = await run_in_threadpool(_compute)
        self.budget_rows = budget
        self.compliance_rows = compliance
        self.evidence_rows = evidence
        self.approval_rows = approval
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh the four review buckets."""

        await self._refresh()


__all__ = ["FinanceReviewState"]
