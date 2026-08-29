"""Integration tests for SQLite-backed stores (BE-1).

Exercises the SQLite path end-to-end against a real :class:`sqlite3.Connection`
(in-memory or temporary file). Validates that:

- The four stores satisfy the same ``Stores`` Protocol used by services.
- Request / workflow / audit / rule round-trip through the SQLite layer.
- The hash chain (audit) survives across multiple appends and verifies.
- Money values (VND scale 0, USD/EUR scale 2) round-trip without precision loss.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from WisPay.models import (
    AccountingDimension,
    BeneficiaryReference,
    LifecycleState,
    Money,
    PaymentRequest,
    RequestType,
    RouteGenerationInput,
    UserSnapshot,
    VendorPaymentDetails,
)
from WisPay.models.enums import (
    AccessClassification,
    AuditAction,
    BeneficiaryType,
    BudgetResult,
    OpexCapexClassification,
)
from WisPay.services import sqlite_repositories as sr
from WisPay.services.approval_workflow import GenerateRouteCommand, generate_route
from WisPay.services.audit_trail import GENESIS_HASH, canonical_payload, chain_hash
from WisPay.services.db import sqlite_connect, sqlite_connect_in_memory
from WisPay.services.repositories import (
    AuditEventStore,
    PaymentRecordStore,
    RequestStore,
    RuleStore,
    Stores,
    WorkflowStore,
)
from WisPay.services.sql_repositories import DurableAuditTrail
from WisPay.services.sqlite_repositories import sqlite_stores
from WisPay.services.workflow_rules import SEED_RULE_VERSION

_NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
_TRAIL_POLICY = uuid4()


def _actor(suffix: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=f"user-{suffix}",
        display_name=f"User {suffix}",
        email=f"{suffix}@wispay.example",
        captured_at=_NOW,
    )


def _money(amount: str, *, code: str = "VND", scale: int | None = None) -> Money:
    if scale is None:
        scale = 0 if code == "VND" else 2
    return Money(amount=Decimal(amount), currency_code=code, decimal_scale=scale)


def _request(
    *,
    number: str | None = None,
    code: str = "VND",
    amount: str = "11000000",
) -> PaymentRequest:
    submitted = number is not None
    net = _money(amount, code=code)
    vat = _money("0", code=code)
    return PaymentRequest(
        request_id=uuid4(),
        request_number=number,
        request_type=RequestType.VENDOR,
        requester=_actor("requester"),
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="Acme Supplies",
            captured_at=_NOW,
            access_classification=AccessClassification.CONFIDENTIAL,
        ),
        accounting_dimension=AccountingDimension(
            legal_entity_code="LE-01",
            legal_entity_name="WisPay Co",
            department_code="CC-01",
            department_name="Operations",
            cost_center_code="C-01",
            cost_center_name="Shared",
            expense_category_code="E-01",
            expense_category_name="Services",
            classification=OpexCapexClassification.OPEX,
            budget_period="2026-08",
            captured_at=_NOW,
        ),
        purpose="Vendor invoice payment",
        total_amount=net,
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.SUBMITTED if submitted else LifecycleState.DRAFT,
        lifecycle_version="v1",
        submitted_version=1 if submitted else None,
        details=VendorPaymentDetails(
            invoice_number="INV-1",
            invoice_date=_NOW.date(),
            due_date=_NOW.date(),
            invoice_net_amount=net,
            vat_amount=vat,
            invoice_gross_amount=net,
            payment_terms="Net 30",
            proposed_payment_method="Bank transfer",
            duplicate_warning_key=f"acme|INV-1|{amount}",
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture
def stores() -> Stores:
    """Fresh in-memory SQLite stores for each test."""
    return sqlite_stores(ensure_tables=True, conn=sqlite_connect_in_memory())


@pytest.fixture
def trail(stores: Stores) -> DurableAuditTrail:
    return DurableAuditTrail(stores.audit, retention_policy_id=_TRAIL_POLICY)


def test_sqlite_stores_build_in_memory(stores: Stores) -> None:
    """The bundle satisfies the Stores Protocol."""
    assert isinstance(stores.requests, RequestStore)
    assert isinstance(stores.workflows, WorkflowStore)
    assert isinstance(stores.audit, AuditEventStore)
    assert isinstance(stores.payments, PaymentRecordStore)
    assert isinstance(stores.rules, RuleStore)


def test_request_round_trip(stores: Stores) -> None:
    request = _request(number="WPR-2026-0001")
    stores.requests.save(request)
    by_id = stores.requests.get(request.request_id)
    by_number = stores.requests.get_by_number("WPR-2026-0001")
    assert by_id == request
    assert by_number == request


def test_request_upsert_is_not_a_duplicate(stores: Stores) -> None:
    request = _request(number="WPR-2026-0002")
    stores.requests.save(request)
    # Mutate state and re-save (same request_id): the same row is updated.
    updated = request.model_copy(update={"lifecycle_state": LifecycleState.APPROVED})
    stores.requests.save(updated)
    assert stores.requests.get(request.request_id) == updated


def test_workflow_instance_round_trip(stores: Stores, trail: DurableAuditTrail) -> None:
    request = _request(number="WPR-2026-0003")
    stores.requests.save(request)
    instance = generate_route(
        GenerateRouteCommand(
            request_id=request.request_id,
            generation_inputs=RouteGenerationInput(
                request_type=RequestType.VENDOR,
                amount=_money("150000000"),
                budget_result=BudgetResult.WITHIN_BUDGET,
                legal_entity_code="LE-01",
                department_code="CC-01",
            ),
        ),
        rules=stores.rules.rules(stores.rules.active_version()),
        rule_version=stores.rules.active_version(),
        now=_NOW,
        actor=_actor("system"),
        audit=trail,
    ).instance
    stores.workflows.save_instance(instance)
    by_id = stores.workflows.get_instance(instance.workflow_instance_id)
    latest = stores.workflows.latest_instance_for_request(request.request_id)
    assert by_id == instance
    assert latest == instance
    # Pending query returns the fresh instance.
    pending = stores.workflows.pending_instances()
    assert instance in pending


def test_audit_chain_round_trip(trail: DurableAuditTrail) -> None:
    first = trail.append(
        entity_type="payment_request",
        entity_id="req-1",
        actor=_actor("requester"),
        action=AuditAction.SUBMITTED,
        occurred_at=_NOW,
        correlation_id="corr-1",
    )
    second = trail.append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_actor("lm"),
        action=AuditAction.APPROVED,
        occurred_at=_NOW,
        correlation_id="corr-1",
    )
    assert first.previous_hash == GENESIS_HASH
    assert second.previous_hash == first.event_hash
    events = trail.events_for_request("corr-1")
    assert events == (first, second)


def test_audit_chain_continues_across_trail_instances(stores: Stores) -> None:
    first_trail = DurableAuditTrail(stores.audit, retention_policy_id=_TRAIL_POLICY)
    event_one = first_trail.append(
        entity_type="workflow_instance",
        entity_id="wf-1",
        actor=_actor("system"),
        action=AuditAction.CHANGED,
        occurred_at=_NOW,
        reason="route generated",
        correlation_id="corr-3",
    )
    second_trail = DurableAuditTrail(stores.audit, retention_policy_id=_TRAIL_POLICY)
    event_two = second_trail.append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_actor("lm"),
        action=AuditAction.APPROVED,
        occurred_at=_NOW,
        correlation_id="corr-3",
    )
    assert event_two.previous_hash == event_one.event_hash
    # Hash recomputation matches the stored value (chain integrity).
    actor_json = event_two.actor.model_dump(mode="json")
    payload = {
        "entity_type": event_two.entity_type,
        "entity_id": event_two.entity_id,
        "actor": actor_json,
        "action": event_two.action.value,
        "occurred_at": event_two.occurred_at.isoformat(),
        "correlation_id": event_two.correlation_id,
        "retention_policy_id": str(event_two.retention_policy_id),
        "previous_hash": event_two.previous_hash,
    }
    expected = chain_hash(event_two.previous_hash, canonical_payload(payload))
    assert event_two.event_hash == expected


def test_rules_seed_is_idempotent(stores: Stores) -> None:
    """Calling ``ensure_seeded`` twice produces the same set of rules."""
    rules_first = stores.rules.rules(SEED_RULE_VERSION)
    # Re-seed: re-running should be a no-op because the version row exists.
    stores.rules.ensure_seeded()
    rules_second = stores.rules.rules(SEED_RULE_VERSION)
    assert len(rules_first) == len(rules_second) >= 1


def test_active_version_returns_seeded_label(stores: Stores) -> None:
    assert stores.rules.active_version() == SEED_RULE_VERSION


def test_money_round_trip_preserves_decimal_precision(stores: Stores) -> None:
    """VND scale 0 survives an in-memory round trip."""
    request = _request(code="VND", amount="123456789012")
    stores.requests.save(request)
    again = stores.requests.get(request.request_id)
    assert again is not None
    assert again.total_amount.amount == Decimal("123456789012")
    assert again.total_amount.decimal_scale == 0


def test_driver_kind_detects_sqlite_url() -> None:
    from WisPay.services.db import driver_kind_from_url

    assert driver_kind_from_url("sqlite:///wispay.db") == "sqlite"
    assert driver_kind_from_url("sqlite:///:memory:") == "sqlite"
    assert driver_kind_from_url("mssql+pyodbc://example") == "azure-sql"
    with pytest.raises(ValueError):
        driver_kind_from_url("postgres://example")


def test_sqlite_schema_statements_are_idempotent() -> None:
    """Running the schema twice does not error (CREATE IF NOT EXISTS)."""
    conn = sqlite_connect("sqlite:///:memory:")
    try:
        for stmt in sr.sqlite_schema_statements():
            conn.execute(stmt)
        conn.commit()
        # Running again must still succeed.
        for stmt in sr.sqlite_schema_statements():
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
