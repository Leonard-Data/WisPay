"""Unit coverage for draft validation, aggregate construction, and submission."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from WisPay.models import LifecycleState, PaymentRequest, VendorPaymentDetails
from WisPay.services.audit_trail import InMemoryAuditTrail
from WisPay.services.reference_data import REQUESTER_PROTOTYPE
from WisPay.services.request_creation import (
    DraftCommand,
    SubmissionResult,
    build_payment_request,
    duplicate_scan,
    gross_of,
    parse_money,
    submit_request,
    validate_draft_command,
)

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def vendor_cmd(**overrides: str) -> DraftCommand:
    base = {
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


def employee_cmd(**overrides: str) -> DraftCommand:
    base = {
        "family": "employee",
        "subtype": "reimbursement",
        "title": "Client visit reimbursement",
        "purpose": "Reimburse out-of-pocket travel for the client workshop.",
        "currency": "VND",
        "net_text": "2500000",
        "merchant": "Vietravel",
        "expense_date": "2026-08-20",
        "policy_category": "Travel",
        "requested_payment_date": "2026-09-05",
        "legal_entity": "VN01",
        "cost_center": "CC-200",
        "expense_category": "TRAVEL",
        "classification": "OPEX",
        "budget_period": "2026-08",
    }
    base.update(overrides)
    return DraftCommand(**base)  # type: ignore[arg-type]


def uploaded(*keys: str) -> frozenset[str]:
    return frozenset(keys)


# --- parse_money -------------------------------------------------------------


def test_parse_money_vnd_rejects_decimals() -> None:
    with pytest.raises(ValueError, match="VND"):
        parse_money("10.5", "VND")


def test_parse_money_usd_allows_two_places_only() -> None:
    assert parse_money("12.34", "USD").amount == Decimal("12.34")
    with pytest.raises(ValueError, match="decimal places"):
        parse_money("1.234", "USD")


def test_parse_money_rejects_garbage_negative_and_empty() -> None:
    for bad in ("", "abc", "-5", "1.2.3"):
        with pytest.raises(ValueError):
            parse_money(bad, "VND")


def test_gross_of_adds_same_currency_values() -> None:
    net = parse_money("1000000", "VND")
    vat = parse_money("100000", "VND")
    gross = gross_of(net, vat)
    assert gross.amount == Decimal("1100000")
    assert gross.decimal_scale == 0


# --- validate_draft_command --------------------------------------------------


def test_valid_vendor_command_has_no_issues_without_uploads_blocking() -> None:
    outcome = validate_draft_command(vendor_cmd(), uploaded())
    assert outcome.field_issues == ()
    assert outcome.blocking == ("Attach Invoice.",)


def test_vendor_missing_fields_report_state_var_names() -> None:
    cmd = vendor_cmd(title="", invoice_number="", due_date="", net_text="")
    fields = {issue.field: issue.message for issue in validate_draft_command(cmd).field_issues}
    assert set(fields) >= {"title", "invoice_number", "due_date", "net_text"}


def test_vendor_due_date_before_invoice_date_is_rejected() -> None:
    cmd = vendor_cmd(invoice_date="2026-08-31", due_date="2026-08-01")
    fields = {issue.field for issue in validate_draft_command(cmd).field_issues}
    assert "due_date" in fields


def test_employee_activity_end_before_start_is_rejected() -> None:
    cmd = employee_cmd(
        subtype="advance",
        activity_start="2026-09-10",
        activity_end="2026-09-01",
        expense_date="",
        merchant="",
    )
    fields = {issue.field for issue in validate_draft_command(cmd).field_issues}
    assert "activity_end" in fields


def test_settlement_requires_linked_advance() -> None:
    cmd = employee_cmd(subtype="settlement", linked_advance_id="", policy_category="")
    fields = {issue.field for issue in validate_draft_command(cmd).field_issues}
    assert "linked_advance_id" in fields


def test_unknown_family_short_circuits() -> None:
    outcome = validate_draft_command(DraftCommand(family=""))
    assert [issue.field for issue in outcome.field_issues] == ["family"]


def test_required_documents_surface_as_blocking_messages() -> None:
    outcome = validate_draft_command(employee_cmd(), uploaded("receipt"))
    assert outcome.blocking == ()


def test_accounting_selects_and_period_are_enforced() -> None:
    cmd = vendor_cmd(
        legal_entity="XX", cost_center="YY", classification="WHATEVER", budget_period="August"
    )
    fields = {issue.field for issue in validate_draft_command(cmd).field_issues}
    assert {"legal_entity", "cost_center", "classification", "budget_period"} <= fields


# --- build_payment_request ---------------------------------------------------


def test_build_vendor_aggregate_satisfies_model_invariants() -> None:
    request = build_payment_request(vendor_cmd(), requester=REQUESTER_PROTOTYPE, now=NOW)
    assert isinstance(request.details, VendorPaymentDetails)
    assert request.lifecycle_state is LifecycleState.DRAFT
    assert request.total_amount.amount == Decimal("11000000")
    assert request.accounting_period == "2026-08"
    assert request.request_number is None and request.submitted_version is None


def test_build_employee_reimbursement_maps_claimed_amount() -> None:
    request = build_payment_request(employee_cmd(), requester=REQUESTER_PROTOTYPE, now=NOW)
    assert request.total_amount.amount == Decimal("2500000")
    assert request.beneficiary.beneficiary_type.value == "Employee"
    assert request.details.subtype.value == "Reimbursement"


def test_build_invalid_command_raises_validation_error() -> None:
    with pytest.raises(PydanticValidationError):
        build_payment_request(
            vendor_cmd(due_date="2026-07-01"), requester=REQUESTER_PROTOTYPE, now=NOW
        )


# --- submit_request ----------------------------------------------------------


def submitted(trail: InMemoryAuditTrail, cmd: DraftCommand | None = None) -> SubmissionResult:
    draft = build_payment_request(cmd or vendor_cmd(), requester=REQUESTER_PROTOTYPE, now=NOW)
    return submit_request(
        draft,
        actor=REQUESTER_PROTOTYPE,
        now=NOW,
        request_number="WPR-2026-0001",
        trail=trail,
    )


def test_submit_transitions_to_submitted_with_number() -> None:
    result = submitted(InMemoryAuditTrail())
    assert result.request.lifecycle_state is LifecycleState.SUBMITTED
    assert result.request.request_number == "WPR-2026-0001"
    assert result.request.submitted_version == 1
    assert result.audit_event.action.value == "Submitted"
    assert result.audit_event.new_value is not None


def test_double_submit_is_guarded() -> None:
    trail = InMemoryAuditTrail()
    result = submitted(trail)
    with pytest.raises(ValueError, match="Only draft requests can be submitted"):
        submit_request(
            result.request,
            actor=REQUESTER_PROTOTYPE,
            now=NOW,
            request_number="WPR-2026-0002",
            trail=trail,
        )


def test_submit_appends_verifiable_chain_event() -> None:
    trail = InMemoryAuditTrail()
    result = submitted(trail)
    assert trail.events()[-1].event_hash == result.audit_event.event_hash
    assert trail.verify() is True


# --- duplicate_scan ----------------------------------------------------------


def existing_duplicate(number: str) -> PaymentRequest:
    draft = build_payment_request(
        vendor_cmd(invoice_number=number), requester=REQUESTER_PROTOTYPE, now=NOW
    )
    return submit_request(
        draft,
        actor=REQUESTER_PROTOTYPE,
        now=NOW,
        request_number=f"WPR-2026-{uuid4().hex[:4].upper()}",
        trail=InMemoryAuditTrail(),
    ).request


def test_duplicate_scan_flags_same_vendor_and_invoice() -> None:
    store = [existing_duplicate("INV-DUP")]
    warnings = duplicate_scan(store, vendor_cmd(invoice_number="INV-DUP"))
    assert len(warnings) == 1
    assert "duplicate" in warnings[0]


def test_duplicate_scan_ignores_different_invoice_or_family() -> None:
    store = [existing_duplicate("INV-DUP")]
    assert duplicate_scan(store, vendor_cmd(invoice_number="INV-OTHER")) == ()
    assert duplicate_scan(store, employee_cmd()) == ()


def test_submission_result_holds_uuid_identifiers() -> None:
    result = submitted(InMemoryAuditTrail())
    assert isinstance(result.request.request_id, UUID)
