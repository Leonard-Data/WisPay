"""Approval route generation and decision guards (WorkflowService/ApprovalService).

Pure domain per ADR-0005: no Reflex, no driver, no environment access. Route
snapshots freeze the rule version and generation inputs forever (ADR-0006);
later rule changes never rewrite existing instances. Guards enforce the
CONTEXT.md invariants in the service, not the UI — notably invariant 3: the
requester can never decide their own request.

Hash chaining happens at the store boundary, so both entry points take an
:class:`AuditAppender` (satisfied by ``InMemoryAuditTrail`` and
``DurableAuditTrail``) and return the persisted events to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID, uuid4

from WisPay.models import (
    ApprovalDecision,
    ApprovalStep,
    AuditAction,
    AuditEvent,
    RouteGenerationInput,
    UserSnapshot,
    WorkflowInstance,
)
from WisPay.models._base import WisPayBaseModel
from WisPay.services.audit_trail import canonical_payload
from WisPay.services.workflow_rules import WorkflowRule, matching_rules

if TYPE_CHECKING:
    from collections.abc import Sequence


class GenerateRouteCommand(WisPayBaseModel):
    """Request a frozen approval route for one request."""

    request_id: UUID
    generation_inputs: RouteGenerationInput


class DecisionCommand(WisPayBaseModel):
    """One approver decision on one pending step."""

    workflow_instance_id: UUID
    step_id: UUID
    decision: Literal[
        ApprovalDecision.APPROVED,
        ApprovalDecision.REJECTED,
        ApprovalDecision.RETURNED,
    ]
    actor: UserSnapshot
    reason: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Freshly generated route plus its persisted generation event."""

    instance: WorkflowInstance
    audit_events: tuple[AuditEvent, ...]


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Updated route snapshot plus persisted decision events."""

    instance: WorkflowInstance
    route_completed: bool
    audit_events: tuple[AuditEvent, ...]


class ApprovalWorkflowError(ValueError):
    """Base class for approval workflow guard failures."""


class NoRouteError(ApprovalWorkflowError):
    """No versioned rule row matches the generation inputs."""


class RouteClosedError(ApprovalWorkflowError):
    """The route already reached an outcome or the step is already decided."""


class UnknownStepError(ApprovalWorkflowError):
    """The referenced step does not belong to this workflow instance."""


class NotCurrentStepError(ApprovalWorkflowError):
    """Only the earliest pending sequence (or its parallel group) is actionable."""


class SelfApprovalError(ApprovalWorkflowError):
    """The requester can never provide final approval for their own request."""


class UnauthorizedApproverError(ApprovalWorkflowError):
    """Only the snapshotted step approver may act on the step."""


class MissingReasonError(ApprovalWorkflowError):
    """Rejections and returns require an explicit reason."""


class AuditAppender(Protocol):
    """Trail boundary that chains and persists events.

    ``InMemoryAuditTrail.append`` and ``DurableAuditTrail.append`` satisfy this
    shape (their extra defaulted parameters are ignored here).
    """

    def append(
        self,
        *,
        entity_type: str,
        entity_id: str,
        actor: UserSnapshot,
        action: AuditAction,
        occurred_at: datetime,
        new_value: str | None = None,
        reason: str | None = None,
        correlation_id: str,
    ) -> AuditEvent:
        """Persist one chained event and return it."""
        ...


_DECISION_ACTIONS: dict[str, AuditAction] = {
    ApprovalDecision.APPROVED.value: AuditAction.APPROVED,
    ApprovalDecision.REJECTED.value: AuditAction.REJECTED,
    ApprovalDecision.RETURNED.value: AuditAction.RETURNED,
}
_INSTANCE_ENTITY = "workflow_instance"
_STEP_ENTITY = "approval_step"


def _payload_json(model: WisPayBaseModel) -> str:
    return canonical_payload(model.model_dump(mode="json"))


def actionable_sequences(steps: tuple[ApprovalStep, ...]) -> frozenset[int]:
    """Return the sequences currently open for decisions (earliest pending
    sequence plus any parallel-group peers)."""

    pending = [step for step in steps if step.decision is ApprovalDecision.PENDING]
    if not pending:
        return frozenset()
    earliest = min(step.sequence for step in pending)
    groups = {step.parallel_group for step in pending if step.sequence == earliest} - {None}
    group_steps = {step.sequence for step in pending if step.parallel_group in groups}
    return frozenset({earliest}) | group_steps


_actionable_sequences = actionable_sequences


def generate_route(
    cmd: GenerateRouteCommand,
    *,
    rules: Sequence[WorkflowRule],
    rule_version: str,
    now: datetime,
    actor: UserSnapshot,
    audit: AuditAppender,
) -> RouteResult:
    """Generate and snapshot a frozen approval route from applicable rules."""
    matched = matching_rules(rules, cmd.generation_inputs)
    if not matched:
        raise NoRouteError("No approval rules match this request; routing cannot proceed.")
    steps = tuple(
        ApprovalStep(
            step_id=uuid4(),
            sequence=rule.step_sequence,
            parallel_group=rule.parallel_group,
            approver=rule.approver_user,
            role=rule.approver_role,
            due_at=None if rule.due_days is None else now + timedelta(days=rule.due_days),
        )
        for rule in matched
    )
    instance = WorkflowInstance(
        workflow_instance_id=uuid4(),
        request_id=cmd.request_id,
        workflow_rule_version=rule_version,
        generation_inputs=cmd.generation_inputs,
        steps=steps,
        current_step_sequence=min(step.sequence for step in steps),
        generated_at=now,
    )
    event = audit.append(
        entity_type=_INSTANCE_ENTITY,
        entity_id=str(instance.workflow_instance_id),
        actor=actor,
        action=AuditAction.CHANGED,
        occurred_at=now,
        new_value=_payload_json(instance),
        reason=f"Approval route {rule_version} generated",
        correlation_id=str(cmd.request_id),
    )
    return RouteResult(instance=instance, audit_events=(event,))


def decide(
    cmd: DecisionCommand,
    *,
    instance: WorkflowInstance,
    requester_id: str,
    now: datetime,
    trail_appender: AuditAppender,
) -> DecisionResult:
    """Apply one guarded decision and return the updated frozen snapshot."""
    if instance.final_outcome.value != "Pending":
        raise RouteClosedError("This approval route already reached an outcome.")
    target = next(
        (step for step in instance.steps if step.step_id == cmd.step_id),
        None,
    )
    if target is None:
        raise UnknownStepError("This approval step does not belong to the route.")
    if target.decision is not ApprovalDecision.PENDING:
        raise RouteClosedError("This approval step was already decided.")
    actionable = _actionable_sequences(instance.steps)
    if target.sequence not in actionable:
        raise NotCurrentStepError("Earlier approval steps must be decided before this one.")
    if cmd.actor.external_identity_id == requester_id:
        raise SelfApprovalError("The requester cannot approve their own payment request.")
    if cmd.actor.external_identity_id != target.approver.external_identity_id:
        raise UnauthorizedApproverError("Only the assigned approver can act on this step.")
    needs_reason = cmd.decision in {
        ApprovalDecision.REJECTED,
        ApprovalDecision.RETURNED,
    }
    if needs_reason and (cmd.reason is None or not cmd.reason.strip()):
        raise MissingReasonError("A reason is required to reject or return.")

    decided = target.evolve(
        decision=cmd.decision,
        decided_at=now,
        reason=cmd.reason if needs_reason else cmd.reason,
        comments=target.comments + cmd.comments,
    )
    steps = tuple(decided if step.step_id == cmd.step_id else step for step in instance.steps)
    remaining_pending = [
        step.sequence for step in steps if step.decision is ApprovalDecision.PENDING
    ]
    if cmd.decision is ApprovalDecision.APPROVED and not remaining_pending:
        outcome_value = "Approved"
    elif cmd.decision is ApprovalDecision.REJECTED:
        outcome_value = "Rejected"
    elif cmd.decision is ApprovalDecision.RETURNED:
        outcome_value = "Returned"
    else:
        outcome_value = "Pending"
    updated = instance.evolve(
        steps=steps,
        current_step_sequence=min(remaining_pending) if remaining_pending else None,
        final_outcome=outcome_value,
    )
    event = trail_appender.append(
        entity_type=_STEP_ENTITY,
        entity_id=str(cmd.step_id),
        actor=cmd.actor,
        action=_DECISION_ACTIONS[cmd.decision.value],
        occurred_at=now,
        new_value=_payload_json(decided),
        reason=cmd.reason if needs_reason else None,
        correlation_id=str(instance.request_id),
    )
    return DecisionResult(
        instance=updated,
        route_completed=updated.final_outcome.value == "Approved",
        audit_events=(event,),
    )
