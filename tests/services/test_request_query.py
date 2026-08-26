"""Unit coverage for the read-side request query projections."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from WisPay.models import AuditAction, LifecycleState, UserSnapshot
from WisPay.services.audit_trail import InMemoryAuditTrail
from WisPay.services.reference_data import (
    REQUESTER_PROTOTYPE,
    RETENTION_POLICY_ID_PROTOTYPE,
)
from WisPay.services.request_creation import (
    DraftCommand,
    build_payment_request,
    submit_request,
)
from WisPay.services.request_query import (
    QueueQuery,
    RequestAccessDeniedError,
    RequestNotFoundError,
    events_for_request,
    format_money,
    get_request,
    is_overdue,
    payee_display_of,
    queue_rows,
)

NOW = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)
TODAY = date(2026, 8, 26)

OTHER_VIEWER = UserSnapshot(
    external_identity_id="entra-other-viewer",
    display_name="Other Viewer",
    email="other.viewer@wispay.example",
    captured_at=NOW,
)


def vendor_cmd(**overrides: str) -> DraftCommand:
    from tests.services.test_request_creation import vendor_cmd as base

    return base(**overrides)


def employee_cmd(**overrides: str) -> DraftCommand:
    from tests.services.test_request_creation import employee_cmd as base

    return base(**overrides)


def submitted_vendor(number: str, **overrides: str):
    trail = InMemoryAuditTrail()
    draft = build_payment_request(vendor_cmd(**overrides), requester=REQUESTER_PROTOTYPE, now=NOW)
    return submit_request(
        draft, actor=REQUESTER_PROTOTYPE, now=NOW, request_number=number, trail=trail
    ).request


def submitted_employee(number: str, **overrides: str):
    trail = InMemoryAuditTrail()
    draft = build_payment_request(employee_cmd(**overrides), requester=REQUESTER_PROTOTYPE, now=NOW)
    return submit_request(
        draft, actor=REQUESTER_PROTOTYPE, now=NOW, request_number=number, trail=trail
    ).request


def foreign_vendor(number: str):
    trail = InMemoryAuditTrail()
    draft = build_payment_request(vendor_cmd(), requester=OTHER_VIEWER, now=NOW)
    return submit_request(
        draft, actor=OTHER_VIEWER, now=NOW, request_number=number, trail=trail
    ).request


def numbers(rows) -> list[str]:
    return [row.number for row in rows]


# --- queue_rows ---------------------------------------------------------------


def test_queue_excludes_drafts_and_foreign_scope_and_sorts_newest_first() -> None:
    trail = InMemoryAuditTrail()
    draft = build_payment_request(vendor_cmd(), requester=REQUESTER_PROTOTYPE, now=NOW)
    first = submit_request(
        draft, actor=REQUESTER_PROTOTYPE, now=NOW, request_number="WPR-2026-0001", trail=trail
    ).request
    second = submitted_vendor("WPR-2026-0002")
    foreign = foreign_vendor("WPR-2026-0003")

    rows = queue_rows([first, second, foreign], viewer=REQUESTER_PROTOTYPE, today=TODAY)

    assert numbers(rows) == ["WPR-2026-0002", "WPR-2026-0001"]


def test_queue_sorts_number_descending_on_equal_timestamps() -> None:
    a = submitted_vendor("WPR-2026-0007")
    b = submitted_vendor("WPR-2026-0008")
    rows = queue_rows([a, b], viewer=REQUESTER_PROTOTYPE, today=TODAY)
    assert numbers(rows) == ["WPR-2026-0008", "WPR-2026-0007"]


def test_queue_row_projection_carries_labels_and_money() -> None:
    vendor = submitted_vendor("WPR-2026-0010")
    employee = submitted_employee("WPR-2026-0011")
    rows = queue_rows([vendor, employee], viewer=REQUESTER_PROTOTYPE, today=TODAY)

    by_number = {row.number: row for row in rows}
    vendor_row = by_number["WPR-2026-0010"]
    employee_row = by_number["WPR-2026-0011"]

    assert vendor_row.payee_display == "Acme Supplies"
    assert vendor_row.type_label == "Vendor"
    assert vendor_row.subtype_label == ""
    assert vendor_row.state is LifecycleState.SUBMITTED
    assert vendor_row.amount.currency_code == "VND"
    assert isinstance(vendor_row.request_id, UUID)

    assert employee_row.payee_display == "Prototype Requester"
    assert employee_row.type_label == "Employee"
    assert employee_row.subtype_label == "Reimbursement"


def test_queue_search_hits_number_payee_invoice_and_purpose() -> None:
    req = submitted_vendor("WPR-2026-0020")

    for needle in ("wpr-2026-0020", "acme", "inv-1001", "august delivery"):
        rows = queue_rows(
            [req], viewer=REQUESTER_PROTOTYPE, today=TODAY, query=QueueQuery(search_text=needle)
        )
        assert numbers(rows) == ["WPR-2026-0020"], needle

    miss = queue_rows(
        [req], viewer=REQUESTER_PROTOTYPE, today=TODAY, query=QueueQuery(search_text="nomatch")
    )
    assert miss == ()


def test_queue_status_family_and_cost_center_filters() -> None:
    vendor = submitted_vendor("WPR-2026-0030")
    employee = submitted_employee("WPR-2026-0031")
    both = [vendor, employee]

    status = queue_rows(
        both,
        viewer=REQUESTER_PROTOTYPE,
        today=TODAY,
        query=QueueQuery(status=LifecycleState.SUBMITTED.value),
    )
    assert numbers(status) == ["WPR-2026-0031", "WPR-2026-0030"]

    family = queue_rows(
        both, viewer=REQUESTER_PROTOTYPE, today=TODAY, query=QueueQuery(family="Employee")
    )
    assert numbers(family) == ["WPR-2026-0031"]

    cost_center = queue_rows(
        both, viewer=REQUESTER_PROTOTYPE, today=TODAY, query=QueueQuery(cost_center="CC-100")
    )
    assert numbers(cost_center) == ["WPR-2026-0030"]


# --- overdue ------------------------------------------------------------------


def test_overdue_boundaries_follow_spec_decision_seven() -> None:
    overdue_yesterday = submitted_vendor("WPR-2026-0040", due_date="2026-08-25")
    due_today = submitted_vendor("WPR-2026-0041", due_date="2026-08-26")
    employee = submitted_employee("WPR-2026-0042")

    assert is_overdue(overdue_yesterday, today=TODAY) is True
    assert overdue_yesterday.evolve(lifecycle_state=LifecycleState.SUBMITTED).lifecycle_state is (
        LifecycleState.SUBMITTED
    )  # evolve guard sanity for the next assertion
    paid = overdue_yesterday.evolve(lifecycle_state=LifecycleState.PAID)
    assert is_overdue(paid, today=TODAY) is False
    assert is_overdue(due_today, today=TODAY) is False
    assert is_overdue(employee, today=TODAY) is False


def test_queue_flags_overdue_chip_source() -> None:
    overdue = submitted_vendor("WPR-2026-0050", due_date="2026-08-01")
    fresh = submitted_vendor("WPR-2026-0051")
    rows = {
        row.number: row
        for row in queue_rows([overdue, fresh], viewer=REQUESTER_PROTOTYPE, today=TODAY)
    }
    assert rows["WPR-2026-0050"].overdue is True
    assert rows["WPR-2026-0051"].overdue is False


# --- get_request ---------------------------------------------------------------


def test_get_request_returns_match_for_owner() -> None:
    req = submitted_vendor("WPR-2026-0060")
    assert get_request([req], number="WPR-2026-0060", viewer=REQUESTER_PROTOTYPE) is req


def test_get_request_unknown_number_raises_not_found() -> None:
    with pytest.raises(RequestNotFoundError) as info:
        get_request([], number="WPR-2026-9999", viewer=REQUESTER_PROTOTYPE)
    assert info.value.number == "WPR-2026-9999"


def test_get_request_foreign_owner_raises_access_denied() -> None:
    foreign = foreign_vendor("WPR-2026-0070")
    with pytest.raises(RequestAccessDeniedError):
        get_request([foreign], number="WPR-2026-0070", viewer=REQUESTER_PROTOTYPE)


# --- format_money ---------------------------------------------------------------


def test_format_money_uses_stored_scale_per_currency() -> None:
    vnd = submitted_vendor("WPR-2026-0080").total_amount
    usd = submitted_vendor(
        "WPR-2026-0081", currency="USD", net_text="1100.00", vat_text="134.50"
    ).total_amount

    assert format_money(vnd) == "11,000,000 VND"
    assert format_money(usd) == "1,234.50 USD"


# --- events_for_request ----------------------------------------------------------


def _decoy(event_id: UUID, occurred_at: datetime):
    trail = InMemoryAuditTrail()
    return trail.append(
        entity_type="ApprovalStep",
        entity_id=str(event_id),
        actor=REQUESTER_PROTOTYPE,
        action=AuditAction.REVIEWED,
        occurred_at=occurred_at,
        correlation_id=f"submit:{event_id}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )


def test_events_select_by_entity_and_order_chronologically() -> None:
    req = submitted_vendor("WPR-2026-0090")
    rid = req.request_id
    later = NOW + timedelta(hours=1)

    trail = InMemoryAuditTrail()
    first = trail.append(
        entity_type="PaymentRequest",
        entity_id=str(rid),
        actor=REQUESTER_PROTOTYPE,
        action=AuditAction.SUBMITTED,
        occurred_at=later,
        correlation_id=f"submit:{rid}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    second = trail.append(
        entity_type="PaymentRequest",
        entity_id=str(rid),
        actor=REQUESTER_PROTOTYPE,
        action=AuditAction.CHANGED,
        occurred_at=NOW + timedelta(hours=2),
        correlation_id="change:op-2",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    decoy_same_correlation = _decoy(rid, NOW + timedelta(minutes=30))
    other_request = _decoy(uuid4(), NOW + timedelta(minutes=45))

    events = events_for_request(
        [second, decoy_same_correlation, first, other_request], request_id=rid
    )

    assert [event.action for event in events] == [AuditAction.SUBMITTED, AuditAction.CHANGED]
    assert all(event.entity_type == "PaymentRequest" for event in events)


def test_payee_display_follows_canonical_beneficiary_snapshot() -> None:
    vendor = submitted_vendor("WPR-2026-0100")
    employee = submitted_employee("WPR-2026-0101")
    assert payee_display_of(vendor) == "Acme Supplies"
    # Employee requests pay the requester-employee; merchant text is metadata.
    assert payee_display_of(employee) == "Prototype Requester"
