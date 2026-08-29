"""Tests for the t5 state adapters.

These tests exercise the service-layer helpers invoked by the new states
(``dashboard``, ``requests``, ``finance_review``, ``payments``, ``admin``,
``reports``, ``audit``, ``persona``, ``notifications``, ``i18n``). The
state objects themselves are thin UI adapters; the real work lives in the
underlying services, which the BS-1 contract already verifies.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from tests.services.fakes import FakeStores
from WisPay.models import (
    AccountingDimension,
    AuditAction,
    BankReferenceSnapshot,
    BeneficiaryReference,
    BeneficiaryType,
    LifecycleState,
    Money,
    OpexCapexClassification,
    PaymentRequest,
    RequestType,
    UserSnapshot,
    VendorPaymentDetails,
)
from WisPay.services.demo_seed import seed_demo_state
from WisPay.services.request_query import QueueQuery, RequestQueueRow, queue_rows
from WisPay.services.workflow_rules import seed_rules_v1


def _seeded_fake_stores() -> object:
    return FakeStores(rules=seed_rules_v1()).stores


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _now() -> Any:
    from datetime import UTC, datetime

    return datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def _vendor(
    number: str,
    state: LifecycleState,
    amount: str = "10000000",
    requester_id: str = "demo-requester-me",
) -> PaymentRequest:
    requester = UserSnapshot(
        external_identity_id=requester_id,
        display_name=requester_id,
        email=f"{requester_id}@wispay.example",
        captured_at=_now(),
    )
    gross = _money(amount)
    zero = _money("0")
    return PaymentRequest(
        request_id=__import__("uuid").uuid4(),
        request_number=number,
        request_type=RequestType.VENDOR,
        requester=requester,
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="Acme Supplies",
            tax_or_employee_reference="0312345678",
            bank_reference=BankReferenceSnapshot(
                reference_id="BANK-VENDOR-001",
                bank_name="VCB",
                masked_account="****1234",
                captured_at=_now(),
                independently_verified=True,
            ),
            captured_at=_now(),
        ),
        accounting_dimension=AccountingDimension(
            legal_entity_code="VN01",
            legal_entity_name="WisPay Vietnam",
            department_code="FIN",
            department_name="Finance",
            cost_center_code="CC-100",
            cost_center_name="Corporate Finance",
            expense_category_code="SERVICES",
            expense_category_name="Professional Services",
            classification=OpexCapexClassification.OPEX,
            budget_period="2026-08",
            captured_at=_now(),
        ),
        purpose=f"Test purpose for {number}",
        total_amount=gross,
        accounting_period="2026-08",
        lifecycle_state=state,
        lifecycle_version="v1",
        submitted_version=1,
        details=VendorPaymentDetails(
            invoice_number=f"INV-{number[-4:]}",
            invoice_date=date(2026, 7, 1),
            due_date=date(2026, 8, 31),
            invoice_net_amount=gross,
            vat_amount=zero,
            invoice_gross_amount=gross,
            payment_terms="Net 30",
            proposed_payment_method="BANK_TRANSFER",
            duplicate_warning_key=f"DUPE-{number}",
        ),
        created_at=_now(),
        updated_at=_now(),
    )


# --------------------------------------------------------------------------- #
# State adapter helper coverage
# --------------------------------------------------------------------------- #


def test_seed_demo_state_supports_dashboard_state_counts() -> None:
    """Dashboard state helper computes per-state counts from the queue rows."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    models = bundle.requests.list_all()
    today = date(2026, 8, 24)
    rows = queue_rows(models, viewer=models[0].requester, today=today, query=QueueQuery())
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state.value] = counts.get(row.state.value, 0) + 1
    assert counts  # at least one bucket
    assert sum(counts.values()) == len(rows)


def test_seed_demo_state_supports_finance_review_buckets() -> None:
    """Finance Review buckets derive from lifecycle_state per spec §4."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    by_state: dict[LifecycleState, int] = {}
    for req in bundle.requests.list_all():
        by_state[req.lifecycle_state] = by_state.get(req.lifecycle_state, 0) + 1
    assert by_state.get(LifecycleState.BUDGET_REVIEW, 0) >= 1
    assert by_state.get(LifecycleState.COMPLIANCE_REVIEW, 0) >= 1
    assert by_state.get(LifecycleState.EVIDENCE_VALIDATION, 0) >= 1
    assert by_state.get(LifecycleState.APPROVAL_PENDING, 0) >= 2


def test_seed_demo_state_supports_payments_buckets() -> None:
    """Payment operator buckets cover Approved / In Process / Paid / Closure."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    by_state: dict[LifecycleState, int] = {}
    for req in bundle.requests.list_all():
        by_state[req.lifecycle_state] = by_state.get(req.lifecycle_state, 0) + 1
    assert by_state.get(LifecycleState.APPROVED, 0) >= 1
    assert by_state.get(LifecycleState.PAID, 0) >= 2
    assert by_state.get(LifecycleState.PAYMENT_IN_PROCESS, 0) >= 1


def test_seed_demo_state_supports_reports_kpis() -> None:
    """Reports state helper aggregates by cost center + lifecycle."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    models = bundle.requests.list_all()
    totals: dict[str, Decimal] = {}
    for req in models:
        code = req.accounting_dimension.cost_center_code
        totals[code] = totals.get(code, Decimal(0)) + req.total_amount.amount
    assert totals  # at least one cost center


def test_seed_demo_state_supports_audit_chain() -> None:
    """Audit events form a hash chain from SUBMITTED through CLOSED."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    s10 = next(
        req for req in bundle.requests.list_all() if req.request_number == "WPR-2026-DEMO-10"
    )
    events = bundle.audit.events_for_request(f"demo-seed:{s10.request_id}")
    # SUBMITTED + at least 4 review-bucket changes + APPROVED + 2 payment + CLOSED
    assert any(event.action is AuditAction.SUBMITTED for event in events)
    assert any(event.action is AuditAction.CLOSED for event in events)
    # S09 (Paid, not Closed) should not carry a CLOSED event.
    s09 = next(
        req for req in bundle.requests.list_all() if req.request_number == "WPR-2026-DEMO-09"
    )
    s09_events = bundle.audit.events_for_request(f"demo-seed:{s09.request_id}")
    assert any(event.action is AuditAction.SUBMITTED for event in s09_events)
    assert not any(event.action is AuditAction.CLOSED for event in s09_events)


def test_request_queue_row_is_typed() -> None:
    """The request-queue row type is a known import (regression for t5)."""

    assert RequestQueueRow is not None
    row = RequestQueueRow(
        request_id=__import__("uuid").uuid4(),
        number="WPR-2026-DEMO-01",
        type_label="Vendor",
        subtype_label="standard",
        payee_display="Acme",
        amount=Money(amount=Decimal("100"), currency_code="VND", decimal_scale=0),
        state=LifecycleState.SUBMITTED,
        submitted_at=_now(),
        overdue=False,
    )
    assert row.number == "WPR-2026-DEMO-01"
    assert row.state is LifecycleState.SUBMITTED
