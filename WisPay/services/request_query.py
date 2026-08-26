"""Read-side query projections for the Payment Request tracking surfaces.

First read/query convention in this repo (flagged as an ADR candidate): pure
functions that take aggregates plus a viewer and return typed projections or
raise typed errors. Mirrors the ADR-0005 service seam on the read side — no
Reflex imports, no I/O, no authorization beyond scope checks derived from the
canonical role matrix (Requester sees ``Own requests``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from WisPay.models import (
    AuditEvent,
    EmployeePaymentDetails,
    LifecycleState,
    Money,
    PaymentRequest,
    UserSnapshot,
    VendorPaymentDetails,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

# Spec decision 7: Overdue applies to vendor requests between submission and
# payment processing. The docs define the inputs but no formula; this window
# is the app-level choice recorded in .scratch/request-tracking/spec.md.
_OVERDUE_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.SUBMITTED,
        LifecycleState.BUDGET_REVIEW,
        LifecycleState.COMPLIANCE_REVIEW,
        LifecycleState.EVIDENCE_VALIDATION,
        LifecycleState.APPROVAL_PENDING,
        LifecycleState.APPROVED,
        LifecycleState.PAYMENT_IN_PROCESS,
    }
)

_MIN_SORT_TIME: datetime = datetime(1, 1, 1, tzinfo=UTC)

_PAYEE_FALLBACK = "\u2014"  # em dash, per design-system empty-value convention


class RequestNotFoundError(LookupError):
    """No visible submitted request matches the requested number."""

    def __init__(self, number: str) -> None:
        self.number = number
        super().__init__(f"No Payment Request with number {number!r}.")


class RequestAccessDeniedError(PermissionError):
    """The requesting viewer is not scoped to see this Payment Request."""


@dataclass(frozen=True, slots=True)
class RequestQueueRow:
    """Display projection for one queue row; masking-safe by construction."""

    request_id: UUID
    number: str
    payee_display: str
    type_label: str
    subtype_label: str
    amount: Money
    state: LifecycleState
    overdue: bool
    submitted_at: datetime | None


@dataclass(frozen=True, slots=True)
class QueueQuery:
    """Queue filters; empty strings mean *All*."""

    search_text: str = ""
    status: str = ""
    family: str = ""
    cost_center: str = ""


_EMPTY_QUERY: QueueQuery = QueueQuery()


def payee_display_of(request: PaymentRequest) -> str:
    """Return the masked-safe payee name from the canonical beneficiary snapshot.

    ``BeneficiaryReference`` on the aggregate root is authoritative for both
    families: vendor requests carry the vendor name, employee requests carry
    the employee (who is the requester in this domain model); the merchant or
    payee text on employee details is descriptive metadata, not the payee.
    """

    return request.beneficiary.display_name or _PAYEE_FALLBACK


def is_overdue(request: PaymentRequest, *, today: date) -> bool:
    """Vendor requests past their due date inside the open processing window."""

    details = request.details
    if not isinstance(details, VendorPaymentDetails):
        return False
    if request.lifecycle_state not in _OVERDUE_STATES:
        return False
    return details.due_date < today


def _matches_query(request: PaymentRequest, payee: str, *, query: QueueQuery) -> bool:
    if query.status and request.lifecycle_state.value != query.status:
        return False
    if query.family and request.request_type.value != query.family:
        return False
    if query.cost_center and request.accounting_dimension.cost_center_code != query.cost_center:
        return False
    needle = query.search_text.strip().casefold()
    if needle:
        details = request.details
        invoice = details.invoice_number if isinstance(details, VendorPaymentDetails) else ""
        haystack = " ".join(
            part for part in (request.request_number or "", payee, invoice, request.purpose) if part
        ).casefold()
        if needle not in haystack:
            return False
    return True


def queue_rows(
    requests: Sequence[PaymentRequest],
    *,
    viewer: UserSnapshot,
    today: date,
    query: QueueQuery = _EMPTY_QUERY,
) -> tuple[RequestQueueRow, ...]:
    """Project, scope, filter, and sort the queue for one viewer.

    Scope follows the canonical Requester visibility ("Own requests"): rows
    whose requester differs from the viewer are filtered out silently here,
    while :func:`get_request` raises for direct lookups. Drafts are never
    tracked. Sorting is newest submission first, then number descending.
    """

    rows: list[RequestQueueRow] = []
    for request in requests:
        if request.lifecycle_state is LifecycleState.DRAFT:
            continue
        if request.requester.external_identity_id != viewer.external_identity_id:
            continue
        payee = payee_display_of(request)
        if not _matches_query(request, payee, query=query):
            continue
        details = request.details
        subtype = details.subtype.value if isinstance(details, EmployeePaymentDetails) else ""
        rows.append(
            RequestQueueRow(
                request_id=request.request_id,
                number=request.request_number or "",
                payee_display=payee or _PAYEE_FALLBACK,
                type_label=request.request_type.value,
                subtype_label=subtype,
                amount=request.total_amount,
                state=request.lifecycle_state,
                overdue=is_overdue(request, today=today),
                # Submission time: created_at is stamped at draft creation and
                # untouched by later transitions (updated_at drifts instead).
                submitted_at=request.created_at,
            )
        )
    rows.sort(key=lambda row: (row.submitted_at or _MIN_SORT_TIME, row.number), reverse=True)
    return tuple(rows)


def get_request(
    requests: Sequence[PaymentRequest],
    *,
    number: str,
    viewer: UserSnapshot,
) -> PaymentRequest:
    """Return the submitted request with exactly this number, scope-checked."""

    matches = [request for request in requests if request.request_number == number]
    if not matches:
        raise RequestNotFoundError(number)
    request = matches[0]
    if request.requester.external_identity_id != viewer.external_identity_id:
        # Distinct typed error for logs; the UI collapses it to the not-found
        # presentation so numbers of other users are not confirmable.
        raise RequestAccessDeniedError(
            f"Viewer {viewer.external_identity_id!r} cannot view {number!r}."
        )
    return request


def format_money(value: Money) -> str:
    """Render ``"<amount> <CODE>"`` with thousands separators at stored scale."""

    digits = f"{value.amount:,.{value.decimal_scale}f}"
    return f"{digits} {value.currency_code}"


def events_for_request(
    events: Sequence[AuditEvent],
    *,
    request_id: UUID,
) -> tuple[AuditEvent, ...]:
    """Audit history for one request, oldest first.

    Keyed by ``entity_type``/``entity_id``: ``correlation_id`` identifies a
    single operation (e.g. ``submit:<id>``), so it must not select history.
    """

    key = str(request_id)
    matched = [
        event
        for event in events
        if event.entity_type == "PaymentRequest" and event.entity_id == key
    ]
    return tuple(sorted(matched, key=lambda event: event.occurred_at))
