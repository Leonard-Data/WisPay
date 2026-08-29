"""Reports state adapter (success measures + spend analysis + exports).

Read-side projections over the durable store. No driver access (ADR-0005).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.models import Money
from WisPay.services.request_query import format_money
from WisPay.services.runtime import stores

if TYPE_CHECKING:
    from WisPay.models import PaymentRequest


def _aggregate_by_cost_center(models: tuple[PaymentRequest, ...]) -> list[dict[str, str]]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    currency: dict[str, str] = {}
    for req in models:
        code = req.accounting_dimension.cost_center_code
        totals[code] += req.total_amount.amount
        currency[code] = req.total_amount.currency_code
    rows: list[dict[str, str]] = []
    for code, total in sorted(totals.items()):
        money = Money(amount=total, currency_code=currency[code], decimal_scale=0)
        rows.append(
            {
                "cost_center": code,
                "amount_display": format_money(money),
            }
        )
    return rows


def _kpi_rows(models: tuple[PaymentRequest, ...]) -> list[dict[str, str]]:
    submitted = sum(1 for req in models if req.lifecycle_state.value != "Draft")
    total = sum((req.total_amount.amount for req in models), Decimal(0))
    currency = models[0].total_amount.currency_code if models else "VND"
    money = Money(amount=total, currency_code=currency, decimal_scale=0)
    return [
        {"label": "Submitted (sample)", "value": str(submitted)},
        {"label": "Total tracked spend", "value": format_money(money)},
        {"label": "Records, not movement", "value": "WisPay never moves money"},
    ]


class ReportsState(rx.State):
    """KPI + spend analysis + export state for the reports page."""

    kpi_rows: list[dict[str, str]] = []
    spend_by_cost_center: list[dict[str, str]] = []
    spend_by_family: list[dict[str, str]] = []
    spend_by_period: list[dict[str, str]] = []
    load_error: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild every report projection off the event loop."""

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
                _kpi_rows(models),
                _aggregate_by_cost_center(models),
                [],
                [],
                "",
            )

        kpis, by_cost, by_family, by_period, error = await run_in_threadpool(_compute)
        self.kpi_rows = kpis
        self.spend_by_cost_center = by_cost
        self.spend_by_family = by_family
        self.spend_by_period = by_period
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh every report projection."""

        await self._refresh()

    @rx.event
    async def export_csv(self) -> None:
        """Stub export hook; real CSV emission lands with t6."""

        self.load_error = "Export pending — wire in t6."


__all__ = ["ReportsState"]
