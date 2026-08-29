"""Admin state adapter (sample configuration studio).

Thin UI adapter over the rule-store Protocol. Surfaces the active rule
version and the threshold matrix in a renderable form; never imports a
driver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import reflex as rx
from starlette.concurrency import run_in_threadpool

from WisPay.services.runtime import stores

if TYPE_CHECKING:
    from WisPay.services.workflow_rules import WorkflowRule


def _rule_rows(rules: tuple[WorkflowRule, ...]) -> list[dict[str, str]]:
    """Flatten rule rows for the threshold matrix display."""

    return [
        {
            "role": rule.approver_role.value,
            "min_amount": str(rule.min_amount) if rule.min_amount is not None else "—",
            "step_sequence": str(rule.step_sequence),
            "currency": rule.currency_code or "—",
            "version": rule.version,
        }
        for rule in rules
    ]


class AdminState(rx.State):
    """Sample configuration studio state for the admin page."""

    active_version: str = "v1"
    rule_rows: list[dict[str, str]] = []
    load_error: str = ""
    route_simulator_status: str = ""

    async def _refresh(self) -> None:
        """Internal helper: rebuild the rule matrix off the event loop."""

        def _compute() -> tuple[str, list[dict[str, str]], str]:
            try:
                bundle = stores()
            except RuntimeError as exc:
                return "v1", [], str(exc)
            version = bundle.rules.active_version()
            return version, _rule_rows(bundle.rules.rules(version)), ""

        version, rows, error = await run_in_threadpool(_compute)
        self.active_version = version
        self.rule_rows = rows
        self.load_error = error

    @rx.event
    async def refresh(self) -> None:
        """Event entry point: refresh the rule matrix."""

        await self._refresh()

    @rx.event
    async def generate_route(self, request_number: str) -> None:
        """Simulate a frozen approval route for a sample request number."""

        if not request_number.strip():
            self.route_simulator_status = "Enter a request number to simulate."
            return
        self.route_simulator_status = (
            f"Route generation requested for {request_number.strip()} — wire to "
            "WorkflowService in t6."
        )


__all__ = ["AdminState"]
