"""Approvals tracking state: a thin Reflex adapter over the workflow services.

Per ADR-0005 this class collects input, calls one service per intent, and
translates typed errors into messages. It never generates routes, decides
guard outcomes, or writes audit records itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import reflex as rx

from WisPay.models import RouteGenerationInput, UserSnapshot, WorkflowInstance
from WisPay.models._base import WisPayBaseModel
from WisPay.models.enums import BudgetResult
from WisPay.models.lifecycle import LifecycleState
from WisPay.services import approval_workflow
from WisPay.services.reference_data import RETENTION_POLICY_ID_PROTOTYPE
from WisPay.services.runtime import stores
from WisPay.services.sql_repositories import DurableAuditTrail
from WisPay.services.workflow_rules import (
    SAMPLE_APPROVER_EXECUTIVE,
    SAMPLE_APPROVER_LINE_MANAGER,
)


class QueueRow(WisPayBaseModel):
    """One actionable approval step shown in the pending queue."""

    key: str
    request_number: str
    title: str
    beneficiary: str
    amount_display: str
    requester_name: str
    approver_role: str
    due_display: str


class TimelineRow(WisPayBaseModel):
    """One step in the frozen route timeline."""

    sequence: int
    approver_name: str
    approver_role: str
    decision: str
    decided_display: str
    reason: str
    is_current: bool


_SAMPLE_ACTORS: dict[str, UserSnapshot] = {
    "Line Manager": SAMPLE_APPROVER_LINE_MANAGER,
    "Executive Approver": SAMPLE_APPROVER_EXECUTIVE,
}


class approvals_state(rx.State):
    """State for the /approvals tracking surface."""

    queue_rows: list[QueueRow] = []
    timeline_rows: list[TimelineRow] = []
    selected_key: str = ""
    selected_summary: dict[str, str] = {}
    reason_text: str = ""
    route_number: str = ""
    status_message: str = ""
    actor_name: str = "Line Manager"

    @rx.var(cache=True)
    def actor_options(self) -> list[str]:
        return list(_SAMPLE_ACTORS)

    def _actor(self) -> UserSnapshot:
        return _SAMPLE_ACTORS[self.actor_name]

    def _trail(self, bundle: Any) -> DurableAuditTrail:
        return DurableAuditTrail(
            bundle.audit,
            retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
        )

    @rx.event
    def switch_actor(self, name: str) -> None:
        """Act as another sample actor and refresh the queue."""
        if name in _SAMPLE_ACTORS:
            self.actor_name = name
        self.selected_key = ""
        self.selected_summary = {}
        self.timeline_rows = []
        self._refresh_queue()

    @rx.event
    def set_reason(self, value: str) -> None:
        self.reason_text = value

    @rx.event
    def set_route_number(self, value: str) -> None:
        self.route_number = value

    def _refresh_queue(self) -> None:
        """Recompute the pending-decision queue for the current actor."""
        try:
            bundle = stores()
        except RuntimeError as error:
            self.status_message = str(error)
            self.queue_rows = []
            return
        actor = self._actor()
        rows: list[QueueRow] = []
        for instance in bundle.workflows.pending_instances():
            request = bundle.requests.get(instance.request_id)
            if request is None:
                continue
            actionable = approval_workflow.actionable_sequences(instance.steps)
            for step in instance.steps:
                if step.decision.value != "Pending":
                    continue
                if step.sequence not in actionable:
                    continue
                if step.approver.external_identity_id != actor.external_identity_id:
                    continue
                scale = request.total_amount.decimal_scale
                rows.append(
                    QueueRow(
                        key=f"{instance.workflow_instance_id}:{step.step_id}",
                        request_number=request.request_number or "—",
                        title=request.purpose,
                        beneficiary=request.beneficiary.display_name,
                        amount_display=(
                            f"{request.total_amount.amount:>,.{scale}f}"
                            f" {request.total_amount.currency_code}"
                        ),
                        requester_name=request.requester.display_name,
                        approver_role=step.role.value,
                        due_display=(
                            step.due_at.astimezone(UTC).strftime("%d %b %Y")
                            if step.due_at is not None
                            else "—"
                        ),
                    )
                )
        self.queue_rows = rows

    @rx.event
    def load_queue(self) -> None:
        """Event wrapper: refresh the pending-decision queue."""
        self._refresh_queue()

    @rx.event
    def create_route(self) -> None:
        """Generate a frozen approval route for a Submitted request number."""
        number = self.route_number.strip()
        if not number:
            self.status_message = "Enter the request number to route."
            return
        try:
            bundle = stores()
        except RuntimeError as error:
            self.status_message = str(error)
            return
        request = bundle.requests.get_by_number(number)
        if request is None:
            self.status_message = f"No stored request matches {number}."
            return
        if request.lifecycle_state is not LifecycleState.SUBMITTED:
            self.status_message = "Only Submitted requests can enter approval routing."
            return
        existing = bundle.workflows.latest_instance_for_request(request.request_id)
        if existing is not None and existing.final_outcome.value == "Pending":
            self.status_message = "An open approval route already exists for this request."
            return
        rule_version = bundle.rules.active_version()
        command = approval_workflow.GenerateRouteCommand(
            request_id=request.request_id,
            generation_inputs=RouteGenerationInput(
                request_type=request.request_type,
                amount=request.total_amount,
                budget_result=BudgetResult.NOT_APPLICABLE,  # sample default; BudgetReviewService lands later
                legal_entity_code=request.accounting_dimension.legal_entity_code,
                department_code=request.accounting_dimension.department_code,
                project_code=request.accounting_dimension.project_code,
                risk_flags=(),
            ),
        )
        now = datetime.now(UTC)
        try:
            result = approval_workflow.generate_route(
                command,
                rules=bundle.rules.rules(rule_version),
                rule_version=rule_version,
                now=now,
                actor=self._actor(),
                audit=self._trail(bundle),
            )
        except approval_workflow.ApprovalWorkflowError as error:
            self.status_message = str(error)
            return
        bundle.workflows.save_instance(result.instance)
        bundle.requests.save(
            request.evolve(
                workflow_instance_id=result.instance.workflow_instance_id,
                updated_at=now,
            )
        )
        steps = len(result.instance.steps)
        self.status_message = (
            f"Approval route {rule_version} generated with {steps} step(s). "
            "Decisions are recorded evidence — payment movement stays a separate Finance action."
        )
        self.route_number = ""
        self._refresh_queue()

    @rx.event
    def select_row(self, key: str) -> None:
        """Event wrapper: load the selection and its route timeline."""
        self._select(key)

    def _select(self, key: str) -> None:
        """Load the selected decision into the panel and its route timeline."""
        try:
            bundle = stores()
        except RuntimeError as error:
            self.status_message = str(error)
            return
        instance_id_text, _, _step_id_text = key.partition(":")
        try:
            instance_id = UUID(instance_id_text)
        except ValueError:
            self.status_message = "Invalid selection."
            return
        instance = bundle.workflows.get_instance(instance_id)
        if instance is None:
            self.status_message = "That approval route no longer exists."
            return
        request = bundle.requests.get(instance.request_id)
        if request is None:
            self.status_message = "The routed request could not be loaded."
            return
        actionable = approval_workflow.actionable_sequences(instance.steps)
        self.selected_summary = {
            "request_number": request.request_number or "—",
            "title": request.purpose,
            "beneficiary": request.beneficiary.display_name,
            "requester_name": request.requester.display_name,
            "amount_display": (
                f"{request.total_amount.amount:>,.{request.total_amount.decimal_scale}f}"
                f" {request.total_amount.currency_code}"
            ),
            "outcome": instance.final_outcome.value,
        }
        self.timeline_rows = [
            TimelineRow(
                sequence=step.sequence,
                approver_name=step.approver.display_name,
                approver_role=step.role.value,
                decision=step.decision.value,
                decided_display=(
                    step.decided_at.astimezone(UTC).strftime("%d %b %Y %H:%M")
                    if step.decided_at is not None
                    else ""
                ),
                reason=step.reason or "",
                is_current=(
                    step.decision.value == "Pending"
                    and step.sequence in actionable
                    and instance.final_outcome.value == "Pending"
                ),
            )
            for step in sorted(instance.steps, key=lambda item: item.sequence)
        ]

    @rx.event
    def decide(self, decision: str) -> None:
        """Record one guarded decision through the approval service."""
        if not self.selected_key:
            self.status_message = "Select an approval to decide first."
            return
        try:
            bundle = stores()
        except RuntimeError as error:
            self.status_message = str(error)
            return
        instance_id_text, _, step_id_text = self.selected_key.partition(":")
        try:
            command = approval_workflow.DecisionCommand(
                workflow_instance_id=UUID(instance_id_text),
                step_id=UUID(step_id_text),
                decision=decision,  # type: ignore[arg-type]
                actor=self._actor(),
                reason=self.reason_text.strip() or None,
            )
        except ValueError:
            self.status_message = "Invalid selection."
            return
        instance = bundle.workflows.get_instance(command.workflow_instance_id)
        if instance is None:
            self.status_message = "That approval route no longer exists."
            return
        request = bundle.requests.get(instance.request_id)
        requester_id = request.requester.external_identity_id if request else ""
        try:
            result = approval_workflow.decide(
                command,
                instance=instance,
                requester_id=requester_id,
                now=datetime.now(UTC),
                trail_appender=self._trail(bundle),
            )
        except approval_workflow.ApprovalWorkflowError as error:
            self.status_message = str(error)
            return
        bundle.workflows.save_instance(result.instance)
        outcome = result.instance.final_outcome.value
        note = " All required approvals are recorded." if result.route_completed else ""
        self.status_message = f"Decision recorded ({outcome}).{note}"
        self.reason_text = ""
        self._refresh_queue()
        self._select(self.selected_key)

    @rx.event
    def dismiss_status(self) -> None:
        self.status_message = ""


def instance_steps_for(instance: WorkflowInstance) -> list[dict[str, Any]]:
    """Return display rows for a route (used by tests and future surfaces)."""
    return [
        {
            "sequence": step.sequence,
            "decision": step.decision.value,
            "approver": step.approver.display_name,
        }
        for step in sorted(instance.steps, key=lambda item: item.sequence)
    ]
