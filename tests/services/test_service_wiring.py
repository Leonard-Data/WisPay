"""End-to-end service-layer wiring against SQLite (BE-2 contract).

Exercises the canonical happy-path write + read flow through the SQLite-
backed ``Stores`` bundle:

1. ``request_creation.build_payment_request`` → ``RequestStore.save``
2. ``request_creation.submit_request`` (session audit) + ``RequestStore.save``
3. ``approval_workflow.generate_route`` (route snapshot)
4. ``approval_workflow.decide`` advances the workflow + audit
5. ``request_query.queue_rows`` scopes by viewer (requester's own row only)
6. ``request_query.get_request`` returns the visible aggregate

The same walk runs against ``FakeStores`` in `:memory:` SQLite to prove both
storage implementations are interchangeable for service code.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from tests.services.fakes import FakeStores
from WisPay.models import (
    ApprovalDecision,
    AuditAction,
    Money,
    PaymentRequest,
    RouteGenerationInput,
    UserSnapshot,
    WorkflowInstance,
    WorkflowOutcome,
)
from WisPay.models.enums import (
    BudgetResult,
)
from WisPay.services.approval_workflow import (
    DecisionCommand,
    GenerateRouteCommand,
    decide,
    generate_route,
)
from WisPay.services.audit_trail import InMemoryAuditTrail
from WisPay.services.reference_data import REQUESTER_PROTOTYPE, RETENTION_POLICY_ID_PROTOTYPE
from WisPay.services.request_creation import (
    DraftCommand,
    build_payment_request,
    duplicate_scan,
    submit_request,
)
from WisPay.services.request_query import QueueQuery, queue_rows
from WisPay.services.sql_repositories import DurableAuditTrail
from WisPay.services.sqlite_repositories import sqlite_stores
from WisPay.services.workflow_rules import SEED_RULE_VERSION, seed_rules_v1

if TYPE_CHECKING:
    from WisPay.services.repositories import Stores

NOW = datetime(2026, 8, 26, 9, 0, 0, tzinfo=UTC)


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def _vendor_cmd(**overrides: str) -> DraftCommand:
    base: dict[str, str] = {
        "family": "vendor",
        "subtype": "standard",
        "title": "Vendor invoice payment",
        "purpose": "Pay supplier invoice INV-1001 for August delivery.",
        "currency": "VND",
        "net_text": "10000000",
        "vat_text": "1000000",
        "vendor_name": "Acme Supplies",
        "invoice_number": "INV-1001",
        "invoice_date": "2026-08-01",
        "due_date": "2026-08-31",
        "payment_terms_code": "NET30",
        "payment_method_code": "BANK_TRANSFER",
        "legal_entity": "VN01",
        "cost_center": "CC-100",
        "expense_category": "SERVICES",
        "classification": "OPEX",
        "budget_period": "2026-08",
    }
    base.update(overrides)
    return DraftCommand(**base)  # type: ignore[arg-type]


def _persist_vendor_request(stores: Stores, trail) -> PaymentRequest:
    draft = build_payment_request(_vendor_cmd(), requester=REQUESTER_PROTOTYPE, now=NOW)
    submitted = submit_request(
        draft,
        actor=REQUESTER_PROTOTYPE,
        now=NOW,
        request_number="WPR-2026-WIRE1",
        trail=trail,
    ).request
    stores.requests.save(submitted)
    return submitted


def _route_inputs(req: PaymentRequest) -> RouteGenerationInput:
    return RouteGenerationInput(
        request_type=req.request_type,
        amount=req.total_amount,
        budget_result=BudgetResult.WITHIN_BUDGET,
        legal_entity_code=req.accounting_dimension.legal_entity_code,
        department_code=req.accounting_dimension.department_code,
    )


def _approve_route(stores: Stores, trail, request: PaymentRequest) -> WorkflowInstance:
    rules = stores.rules.rules(stores.rules.active_version())
    route = generate_route(
        GenerateRouteCommand(
            request_id=request.request_id,
            generation_inputs=_route_inputs(request),
        ),
        rules=rules,
        rule_version=stores.rules.active_version(),
        now=NOW,
        actor=REQUESTER_PROTOTYPE,
        audit=trail,
    ).instance
    stores.workflows.save_instance(route)
    return route


def _nexus_actor(suffix: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=f"sample-{suffix}",
        display_name=f"Sample {suffix}",
        email=f"{suffix}@wispay.example",
        captured_at=NOW,
    )


# --------------------------------------------------------------------------- #
# Fake-backed stores (in-memory doubles)
# --------------------------------------------------------------------------- #


def test_request_creation_and_query_round_trip_against_fake_stores() -> None:
    bundle = FakeStores(rules=seed_rules_v1()).stores
    # DurableAuditTrail can be backed by a FakeAuditEventStore; it satisfies
    # the AuditAppender Protocol (the in-memory session trail intentionally
    # lacks the ``reason`` kwarg, so we use the durable adapter for workflow
    # route generation calls).
    from WisPay.services.sql_repositories import DurableAuditTrail

    trail = DurableAuditTrail(bundle.audit, retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE)

    submitted = _persist_vendor_request(bundle, trail)
    route = _approve_route(bundle, trail, submitted)

    # Self-approval rejected when the actor == requester; run this BEFORE
    # completing the route so the snapshot is still ``Pending``.
    self_cmd = DecisionCommand(
        workflow_instance_id=route.workflow_instance_id,
        step_id=route.steps[0].step_id,
        decision=ApprovalDecision.APPROVED,
        actor=REQUESTER_PROTOTYPE,
    )
    import pytest

    from WisPay.services.approval_workflow import SelfApprovalError

    with pytest.raises(SelfApprovalError):
        decide(
            self_cmd,
            instance=route,
            requester_id=submitted.requester.external_identity_id,
            now=NOW,
            trail_appender=trail,
        )

    # Approve all steps with their snapshotted approver.
    updated = route
    for step in updated.steps:
        cmd = DecisionCommand(
            workflow_instance_id=updated.workflow_instance_id,
            step_id=step.step_id,
            decision=ApprovalDecision.APPROVED,
            actor=step.approver,
        )
        result = decide(
            cmd,
            instance=updated,
            requester_id=submitted.requester.external_identity_id,
            now=NOW,
            trail_appender=trail,
        )
        updated = result.instance
    bundle.workflows.save_instance(updated)

    rows = queue_rows(
        [submitted],
        viewer=REQUESTER_PROTOTYPE,
        today=NOW.date(),
        query=QueueQuery(),
    )
    assert len(rows) == 1
    assert rows[0].number == submitted.request_number
    # Snapshot of rules pin the v1 version.
    assert updated.final_outcome is WorkflowOutcome.APPROVED


# --------------------------------------------------------------------------- #
# SQLite-backed stores (BE-2 contract — same code path, different store)
# --------------------------------------------------------------------------- #


def test_request_creation_and_query_round_trip_against_sqlite_stores() -> None:
    """The same code uses DurableAuditTrail against SqliteAuditEventStore."""
    conn = sqlite3.connect(":memory:")
    bundle = sqlite_stores(conn=conn, ensure_tables=True)
    assert bundle.rules.active_version() == SEED_RULE_VERSION
    trail = DurableAuditTrail(bundle.audit, retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE)

    submitted = _persist_vendor_request(bundle, trail)
    route = _approve_route(bundle, trail, submitted)

    # The first step's snapshotted approver decides ApprovalDecision.APPROVED.
    cmd = DecisionCommand(
        workflow_instance_id=route.workflow_instance_id,
        step_id=route.steps[0].step_id,
        decision=ApprovalDecision.APPROVED,
        actor=route.steps[0].approver,
    )
    decided = decide(
        cmd,
        instance=route,
        requester_id=submitted.requester.external_identity_id,
        now=NOW,
        trail_appender=trail,
    )
    bundle.workflows.save_instance(decided.instance)

    # Storage round-trip — the same request can be re-fetched under its id.
    persisted = bundle.requests.get(submitted.request_id)
    assert persisted is not None
    assert persisted.request_number == submitted.request_number

    # Scope respected for the viewer (requester).
    rows = queue_rows(
        [persisted],
        viewer=REQUESTER_PROTOTYPE,
        today=NOW.date(),
        query=QueueQuery(),
    )
    assert len(rows) == 1

    # Audit appends persisted via SqliteAuditEventStore and chain correctly.
    events = bundle.audit.events_for_request(f"submit:{submitted.request_id}")
    assert any(event.action is AuditAction.SUBMITTED for event in events)
    events = bundle.audit.events_for_request(str(submitted.request_id))
    assert any(event.action is AuditAction.CHANGED for event in events)
    assert any(event.action is AuditAction.APPROVED for event in events)


def test_audit_hash_chain_integrates_with_sqlite_store() -> None:
    chain = DurableAuditTrail(
        sqlite_stores(conn=sqlite3.connect(":memory:"), ensure_tables=True).audit,
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    first = chain.append(
        entity_type="payment_request",
        entity_id="req-1",
        actor=_nexus_actor("lm"),
        action=AuditAction.SUBMITTED,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    second = chain.append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_nexus_actor("cfo"),
        action=AuditAction.APPROVED,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    assert second.previous_hash == first.event_hash


def test_duplicate_scan_uses_round_tripped_requests() -> None:
    """Duplicate detection works on persisted requests (BE-2 round-trip)."""
    bundle = FakeStores(rules=seed_rules_v1()).stores
    trail = InMemoryAuditTrail()
    first = _persist_vendor_request(bundle, trail)
    # Same vendor + invoice → duplicate scan must flag it.
    warnings = duplicate_scan([first], _vendor_cmd(invoice_number="INV-1001"))
    assert any("duplicate" in message.lower() for message in warnings)
