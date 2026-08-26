"""Tests for approval route generation guards and decision handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.services.fakes import FakeAuditEventStore, durable_trail
from WisPay.models import (
    ApprovalDecision,
    ApprovalStep,
    Money,
    RequestType,
    RouteGenerationInput,
    UserSnapshot,
    WorkflowInstance,
    WorkflowOutcome,
)
from WisPay.models.enums import BudgetResult, RoleName
from WisPay.services.approval_workflow import (
    DecisionCommand,
    GenerateRouteCommand,
    MissingReasonError,
    NoRouteError,
    NotCurrentStepError,
    RouteClosedError,
    SelfApprovalError,
    UnauthorizedApproverError,
    UnknownStepError,
    decide,
    generate_route,
)
from WisPay.services.workflow_rules import seed_rules_v1

_NOW = datetime(2026, 8, 26, 9, 0, 0, tzinfo=UTC)
_REQUESTER_ID = "user-requester"


def _actor(identity: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=identity,
        display_name=identity,
        email=f"{identity}@wispay.example",
        captured_at=_NOW,
    )


def _inputs() -> RouteGenerationInput:
    return RouteGenerationInput(
        request_type=RequestType.VENDOR,
        amount=Money(amount=Decimal("150000000"), currency_code="VND", decimal_scale=0),
        budget_result=BudgetResult.WITHIN_BUDGET,
        legal_entity_code="LE-01",
        department_code="CC-01",
    )


def _route(
    *,
    store: FakeAuditEventStore | None = None,
) -> WorkflowInstance:
    result = generate_route(
        GenerateRouteCommand(request_id=uuid4(), generation_inputs=_inputs()),
        rules=seed_rules_v1(),
        rule_version="v1",
        now=_NOW,
        actor=_actor("user-system"),
        audit=durable_trail(store),
    )
    return result.instance


def _command(
    instance: WorkflowInstance, index: int, identity: str, **kw: object
) -> DecisionCommand:
    return DecisionCommand(
        workflow_instance_id=instance.workflow_instance_id,
        step_id=instance.steps[index].step_id,
        decision=kw.pop("decision", ApprovalDecision.APPROVED),  # type: ignore[arg-type]
        actor=_actor(identity),
        **kw,
    )


def test_generate_route_freezes_snapshot() -> None:
    instance = _route()
    assert instance.final_outcome is WorkflowOutcome.PENDING
    assert [step.sequence for step in instance.steps] == [1, 2]
    assert instance.generation_inputs == _inputs()
    assert instance.steps[0].approver.external_identity_id == "sample-lm-001"
    expected_due = _NOW + timedelta(days=3)
    assert instance.steps[0].due_at == expected_due


def test_generate_route_without_matching_rules_raises() -> None:
    with pytest.raises(NoRouteError):
        generate_route(
            GenerateRouteCommand(request_id=uuid4(), generation_inputs=_inputs()),
            rules=(),
            rule_version="v1",
            now=_NOW,
            actor=_actor("user-system"),
            audit=durable_trail(),
        )


def test_full_approval_completes_route() -> None:
    store = FakeAuditEventStore()
    trail = durable_trail(store)
    instance = _route(store=store)
    first = decide(
        _command(instance, 0, "sample-lm-001"),
        instance=instance,
        requester_id=_REQUESTER_ID,
        now=_NOW,
        trail_appender=trail,
    )
    assert first.route_completed is False
    assert first.instance.current_step_sequence == 2
    second = decide(
        _command(first.instance, 1, "sample-cfo-001"),
        instance=first.instance,
        requester_id=_REQUESTER_ID,
        now=_NOW,
        trail_appender=trail,
    )
    assert second.route_completed is True
    assert second.instance.final_outcome is WorkflowOutcome.APPROVED
    assert second.instance.current_step_sequence is None
    actions = [event.action.value for event in store.events_for_request(str(instance.request_id))]
    assert actions == ["Changed", "Approved", "Approved"]


def test_requester_cannot_decide_own_request() -> None:
    instance = _route()
    with pytest.raises(SelfApprovalError):
        decide(
            _command(instance, 0, _REQUESTER_ID),
            instance=instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=durable_trail(),
        )


def test_non_current_step_blocked_before_approver_check() -> None:
    instance = _route()
    with pytest.raises(NotCurrentStepError):
        decide(
            _command(instance, 1, "sample-cfo-001"),
            instance=instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=durable_trail(),
        )


def test_wrong_approver_on_actionable_step_blocked() -> None:
    instance = _route()
    with pytest.raises(UnauthorizedApproverError):
        decide(
            _command(instance, 0, "sample-cfo-001"),
            instance=instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=durable_trail(),
        )


def test_unknown_step_rejected() -> None:
    instance = _route()
    command = DecisionCommand(
        workflow_instance_id=instance.workflow_instance_id,
        step_id=uuid4(),
        decision=ApprovalDecision.APPROVED,
        actor=_actor("sample-lm-001"),
    )
    with pytest.raises(UnknownStepError):
        decide(
            command,
            instance=instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=durable_trail(),
        )


def test_rejection_requires_reason_and_closes_route() -> None:
    instance = _route()
    trail = durable_trail()
    with pytest.raises(MissingReasonError):
        decide(
            _command(instance, 0, "sample-lm-001", decision=ApprovalDecision.REJECTED),
            instance=instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=trail,
        )
    decided = decide(
        _command(
            instance,
            0,
            "sample-lm-001",
            decision=ApprovalDecision.REJECTED,
            reason="Duplicate invoice",
        ),
        instance=instance,
        requester_id=_REQUESTER_ID,
        now=_NOW,
        trail_appender=trail,
    )
    assert decided.route_completed is False
    assert decided.instance.final_outcome is WorkflowOutcome.REJECTED
    with pytest.raises(RouteClosedError):
        decide(
            _command(decided.instance, 1, "sample-cfo-001"),
            instance=decided.instance,
            requester_id=_REQUESTER_ID,
            now=_NOW,
            trail_appender=trail,
        )


def test_return_keeps_future_steps_pending() -> None:
    instance = _route()
    result = decide(
        _command(
            instance,
            0,
            "sample-lm-001",
            decision=ApprovalDecision.RETURNED,
            reason="Amount does not match invoice",
        ),
        instance=instance,
        requester_id=_REQUESTER_ID,
        now=_NOW,
        trail_appender=durable_trail(),
    )
    assert result.instance.final_outcome is WorkflowOutcome.RETURNED
    assert result.instance.steps[1].decision is ApprovalDecision.PENDING


def test_parallel_group_steps_are_jointly_actionable() -> None:
    def _step(sequence: int, group: str | None, identity: str) -> ApprovalStep:
        return ApprovalStep(
            step_id=uuid4(),
            sequence=sequence,
            parallel_group=group,
            approver=_actor(identity),
            role=RoleName.LINE_MANAGER,
        )

    instance = WorkflowInstance(
        workflow_instance_id=uuid4(),
        request_id=uuid4(),
        workflow_rule_version="v1",
        generation_inputs=_inputs(),
        steps=(
            _step(1, "managers", "lm-a"),
            _step(1, "managers", "lm-b"),
            _step(2, None, "sample-cfo-001"),
        ),
        current_step_sequence=1,
        generated_at=_NOW,
    )
    first = decide(
        _command(instance, 0, "lm-a"),
        instance=instance,
        requester_id="someone-else",
        now=_NOW,
        trail_appender=durable_trail(),
    )
    # Same-group peer remains actionable; later sequence still blocked.
    with pytest.raises(NotCurrentStepError):
        decide(
            _command(first.instance, 2, "sample-cfo-001"),
            instance=first.instance,
            requester_id="someone-else",
            now=_NOW,
            trail_appender=durable_trail(),
        )
    second = decide(
        _command(first.instance, 1, "lm-b"),
        instance=first.instance,
        requester_id="someone-else",
        now=_NOW,
        trail_appender=durable_trail(),
    )
    assert second.instance.current_step_sequence == 2


def test_approval_records_optional_reason_and_comments() -> None:
    instance = _route()
    result = decide(
        _command(instance, 0, "sample-lm-001", comments=("Checked totals.",)),
        instance=instance,
        requester_id=_REQUESTER_ID,
        now=_NOW,
        trail_appender=durable_trail(),
    )
    decided = result.instance.steps[0]
    assert decided.decision is ApprovalDecision.APPROVED
    assert decided.reason is None
    assert decided.comments == ("Checked totals.",)
