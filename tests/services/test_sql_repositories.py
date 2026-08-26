"""Tests for SQL repository parameter builders, queries, and the durable trail."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tests.services.fakes import FakeAuditEventStore, FakeStores
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
from WisPay.services import sql_repositories as sr
from WisPay.services.approval_workflow import GenerateRouteCommand, generate_route
from WisPay.services.audit_trail import (
    GENESIS_HASH,
    _event_payload,
    canonical_payload,
    chain_hash,
)
from WisPay.services.repositories import (
    AuditEventStore,
    RequestStore,
    RuleStore,
    WorkflowStore,
)
from WisPay.services.sql_repositories import DurableAuditTrail
from WisPay.services.workflow_rules import seed_rules_v1

_NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)


def _actor(suffix: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=f"user-{suffix}",
        display_name=f"User {suffix}",
        email=f"{suffix}@wispay.example",
        captured_at=_NOW,
    )


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def _request(*, number: str | None = None) -> PaymentRequest:
    submitted = number is not None
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
        total_amount=_money("11000000"),
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.SUBMITTED if submitted else LifecycleState.DRAFT,
        lifecycle_version="v1",
        submitted_version=1 if submitted else None,
        details=VendorPaymentDetails(
            invoice_number="INV-1",
            invoice_date=_NOW.date(),
            due_date=_NOW.date(),
            invoice_net_amount=_money("10000000"),
            vat_amount=_money("1000000"),
            invoice_gross_amount=_money("11000000"),
            payment_terms="Net 30",
            proposed_payment_method="Bank transfer",
            duplicate_warning_key="acme|INV-1|11000000",
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _route_inputs() -> RouteGenerationInput:
    return RouteGenerationInput(
        request_type=RequestType.VENDOR,
        amount=_money("150000000"),
        budget_result=BudgetResult.WITHIN_BUDGET,
        legal_entity_code="LE-01",
        department_code="CC-01",
    )


def _trail(store: FakeAuditEventStore | None = None) -> DurableAuditTrail:
    return DurableAuditTrail(
        store or FakeAuditEventStore(),
        retention_policy_id=uuid4(),
    )


def test_utc_iso_round_trip_preserves_instant() -> None:
    aware = datetime(2026, 8, 26, 7, 30, 0, tzinfo=UTC)
    restored = sr.parse_utc_iso(sr.utc_iso(aware))
    assert restored == aware
    assert restored.tzinfo is not None


def test_request_params_round_trip_through_json() -> None:
    request = _request(number="WPR-2026-0001")
    params = sr.request_insert_params(request)
    assert len(params) == 6
    restored = PaymentRequest.model_validate_json(str(params[3]))
    assert restored == request


def test_rule_params_map_enums_and_amounts() -> None:
    rule = seed_rules_v1()[1]  # executive VND row
    params = sr.rule_insert_params(rule)
    assert params[0] == "v1"
    assert params[2] is None or params[2] == "Vendor"
    assert isinstance(params[3], str)
    assert Decimal(str(params[3])) == rule.min_amount
    assert params[11] == rule.approver_role.value


def test_audit_params_shape_includes_reason_and_snapshot() -> None:
    event = _trail().append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_actor("lm"),
        action=AuditAction.APPROVED,
        occurred_at=_NOW,
        new_value='{"decision": "Approved"}',
        correlation_id="corr-1",
    )
    params = sr.audit_insert_params(event, recorded_at_utc=sr.utc_iso(_NOW))
    assert len(params) == 14
    assert params[6] is None  # approvals carry no required reason
    assert params[7] == '{"decision": "Approved"}'


def test_rejected_event_requires_reason() -> None:
    trail = _trail()
    with pytest.raises(ValidationError):
        trail.append(
            entity_type="approval_step",
            entity_id="step-1",
            actor=_actor("lm"),
            action=AuditAction.REJECTED,
            occurred_at=_NOW,
            correlation_id="corr-2",
        )
    event = trail.append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_actor("lm"),
        action=AuditAction.REJECTED,
        occurred_at=_NOW,
        reason="Policy violation",
        correlation_id="corr-2",
    )
    assert event.reason == "Policy violation"


def test_durable_chain_continues_across_trail_instances() -> None:
    store = FakeAuditEventStore()
    first = _trail(store)
    event_one = first.append(
        entity_type="workflow_instance",
        entity_id="wf-1",
        actor=_actor("system"),
        action=AuditAction.CHANGED,
        occurred_at=_NOW,
        reason="route generated",
        correlation_id="corr-3",
    )
    second = _trail(store)
    event_two = second.append(
        entity_type="approval_step",
        entity_id="step-1",
        actor=_actor("lm"),
        action=AuditAction.APPROVED,
        occurred_at=_NOW,
        correlation_id="corr-3",
    )
    assert event_one.previous_hash == GENESIS_HASH
    assert event_two.previous_hash == event_one.event_hash
    expected = chain_hash(
        event_two.previous_hash,
        canonical_payload(
            _event_payload(
                entity_type=event_two.entity_type,
                entity_id=event_two.entity_id,
                actor=event_two.actor,
                action=event_two.action,
                occurred_at=event_two.occurred_at,
                new_value=None,
                correlation_id=event_two.correlation_id,
                retention_policy_id=event_two.retention_policy_id,
                previous_hash=event_two.previous_hash,
            )
        ),
    )
    assert event_two.event_hash == expected
    assert len(second.events_for_request("corr-3")) == 2


def test_fakes_satisfy_store_protocols() -> None:
    stores = FakeStores(rules=seed_rules_v1()).stores
    assert isinstance(stores.requests, RequestStore)
    assert isinstance(stores.workflows, WorkflowStore)
    assert isinstance(stores.audit, AuditEventStore)
    assert isinstance(stores.rules, RuleStore)


def test_pending_query_targets_pending_outcome_newest_first() -> None:
    assert "outcome = N'Pending'" in sr._INSTANCES_PENDING
    assert "ORDER BY generated_at_utc DESC" in sr._INSTANCES_PENDING


def test_last_hash_query_orders_by_sequence_desc() -> None:
    assert "TOP 1" in sr._AUDIT_LAST_HASH
    assert "ORDER BY sequence DESC" in sr._AUDIT_LAST_HASH


def test_route_generation_over_seed_rules_produces_snapshot() -> None:
    result = generate_route(
        GenerateRouteCommand(request_id=uuid4(), generation_inputs=_route_inputs()),
        rules=seed_rules_v1(),
        rule_version="v1",
        now=_NOW,
        actor=_actor("system"),
        audit=_trail(),
    )
    assert [step.sequence for step in result.instance.steps] == [1, 2]
    assert result.instance.current_step_sequence == 1
    assert result.audit_events[0].action is AuditAction.CHANGED
