"""Tracking state adapter for ``/requests`` and ``/requests/[number]``.

Thin UI adapter per ADR-0005: scoping, filtering, sorting, overdue
derivation, money formatting, and audit selection live in
``WisPay.services.request_query``; this class only sequences calls,
translates outcomes into renderable vars, and reads sibling session state.

Cross-state seam (verified against installed Reflex 0.9.8,
``reflex/state.py::BaseState.get_state``)::

    parent = await self.get_state(RequestCreateState)

returns the per-session instance of the wizard state; underscore-prefixed
attributes stay server-side (never synced to the client).

Path-parameter seam (verified against the dynamic-routing docs;
``router.page.params`` is deprecated since 0.8.1)::

    number = self.router.url.path.removeprefix("/requests").strip("/")
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.models import LifecycleState
from WisPay.services.reference_data import REQUESTER_PROTOTYPE
from WisPay.services.request_query import (
    QueueQuery,
    RequestNotFoundError,
    events_for_request,
    format_money,
    get_request,
    is_overdue,
    queue_rows,
)

if TYPE_CHECKING:
    from reflex.event import EventSpec

_TONE_BY_STATE: dict[LifecycleState, str] = {
    LifecycleState.DRAFT: "neutral",
    LifecycleState.SUBMITTED: "info",
    LifecycleState.BUDGET_REVIEW: "info",
    LifecycleState.COMPLIANCE_REVIEW: "info",
    LifecycleState.EVIDENCE_VALIDATION: "info",
    LifecycleState.APPROVAL_PENDING: "accent",
    LifecycleState.APPROVED: "ok",
    LifecycleState.PAYMENT_IN_PROCESS: "accent",
    LifecycleState.PAID: "ok",
    LifecycleState.CLOSED: "neutral",
    LifecycleState.RETURNED_FOR_CORRECTION: "warn",
    LifecycleState.REJECTED: "danger",
    LifecycleState.CANCELLED: "neutral",
    LifecycleState.ADJUSTMENT_PROCESS: "warn",
}

_MILESTONES: tuple[str, ...] = (
    "Draft",
    "Submitted",
    "In Review",
    "Approved",
    "Payment in Process",
    "Paid",
    "Closed",
)

_REVIEW_BUCKET_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.BUDGET_REVIEW,
        LifecycleState.COMPLIANCE_REVIEW,
        LifecycleState.EVIDENCE_VALIDATION,
        LifecycleState.APPROVAL_PENDING,
    }
)

_BRANCH_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.RETURNED_FOR_CORRECTION,
        LifecycleState.REJECTED,
        LifecycleState.CANCELLED,
        LifecycleState.ADJUSTMENT_PROCESS,
    }
)

_AMOUNT_NOTE = "WisPay records approvals and payment references; it does not move money."


def _fmt_date(value: datetime | date) -> str:
    """Render ``dd Mon yyyy`` (design-system date convention)."""

    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day:02d} {value.strftime('%b')} {value.year:04d}"


def _fmt_datetime(value: datetime) -> str:
    """Render ``dd Mon yyyy HH:MM`` in UTC for audit rows."""

    return f"{_fmt_date(value)} {value.astimezone(UTC):%H:%M}"


def _milestone_index(state: LifecycleState) -> int:
    """Map a canonical state onto the 7-milestone normal-flow stepper."""

    if state is LifecycleState.DRAFT:
        return 1
    if state is LifecycleState.SUBMITTED:
        return 2
    if state in _REVIEW_BUCKET_STATES:
        return 3
    if state is LifecycleState.APPROVED:
        return 4
    if state is LifecycleState.PAYMENT_IN_PROCESS:
        return 5
    if state is LifecycleState.PAID:
        return 6
    if state is LifecycleState.CLOSED:
        return 7
    if state is LifecycleState.RETURNED_FOR_CORRECTION:
        return 2
    if state is LifecycleState.ADJUSTMENT_PROCESS:
        return 7
    return 3  # Rejected / Cancelled hold their review-stage position


def _stepper_rows(state: LifecycleState) -> list[dict[str, str]]:
    current = _milestone_index(state)
    branched = state in _BRANCH_STATES
    rows: list[dict[str, str]] = []
    for index, label in enumerate(_MILESTONES, start=1):
        if index < current:
            phase = "done"
        elif index == current:
            phase = "branch" if branched else "active"
        else:
            phase = "future"
        rows.append({"label": label, "phase": phase})
    return rows


def _kv(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value or "\u2014"}


class request_tracking_state(rx.State):
    """Queue and detail projections over the session submission store."""

    # Queue vars
    rows: list[dict[str, str]] = []
    search_text: str = ""
    status_filter: str = ""
    family_filter: str = ""
    cost_center_filter: str = ""
    cost_center_options: list[str] = []
    result_count: int = 0
    empty_kind: str = "no-requests"  # "" | no-requests | no-matches
    load_error: str = ""

    # Detail vars
    selected_number: str = ""
    not_found: bool = False
    detail: dict[str, str] = {}
    detail_amount: dict[str, str] = {}
    stepper: list[dict[str, str]] = []
    parties_rows: list[dict[str, str]] = []
    accounting_rows: list[dict[str, str]] = []
    amount_rows: list[dict[str, str]] = []
    doc_rows: list[dict[str, str]] = []
    route_steps: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    audit_count: int = 0
    chain_verified: bool = False

    async def _refresh_queue(self) -> None:
        """Helper: rebuild queue projections (callable from other handlers)."""

        parent = await self.get_state(RequestCreateState)
        models = parent._submitted_models()
        today = date.today()
        self.cost_center_options = sorted(
            {model.accounting_dimension.cost_center_code for model in models}
        )
        query = QueueQuery(
            search_text=self.search_text,
            status=self.status_filter,
            family=self.family_filter,
            cost_center=self.cost_center_filter,
        )
        due_by_number = {
            model.request_number or "": (
                _fmt_date(details)
                if isinstance(
                    details := getattr(model.details, "due_date", None),
                    date,
                )
                else "\u2014"
            )
            for model in models
        }
        projected = queue_rows(models, viewer=REQUESTER_PROTOTYPE, today=today, query=query)
        serialized: list[dict[str, str]] = []
        for row in projected:
            submitted_at = row.submitted_at
            age_days = str((today - submitted_at.date()).days) if submitted_at else ""
            serialized.append(
                {
                    "request_id": str(row.request_id),
                    "number": row.number,
                    "payee": row.payee_display,
                    "type_icon": row.type_label[:1].upper(),
                    "family_subtype": (
                        f"{row.type_label} \u00b7 {row.subtype_label}"
                        if row.subtype_label
                        else row.type_label
                    ),
                    "amount_display": format_money(row.amount),
                    "state": row.state.value,
                    "tone": _TONE_BY_STATE[row.state],
                    "overdue": "Overdue" if row.overdue else "",
                    "submitted_display": _fmt_date(submitted_at) if submitted_at else "\u2014",
                    "age_days": age_days,
                    "due_display": due_by_number.get(row.number, "\u2014"),
                }
            )
        self.rows = serialized
        self.result_count = len(serialized)
        submitted_total = len(parent.submitted_requests)
        if submitted_total == 0:
            self.empty_kind = "no-requests"
        elif self.result_count == 0:
            self.empty_kind = "no-matches"
        else:
            self.empty_kind = ""

    @rx.event
    async def refresh_queue(self) -> None:
        """Event entry point for queue projection refresh."""

        await self._refresh_queue()

    @rx.event
    async def set_search(self, value: str) -> None:
        """Store the search text and re-project."""

        self.search_text = value
        await self._refresh_queue()

    @rx.event
    async def set_status(self, value: str) -> None:
        """Store the status filter and re-project."""

        self.status_filter = value
        await self._refresh_queue()

    @rx.event
    async def set_family(self, value: str) -> None:
        """Store the family filter and re-project."""

        self.family_filter = value
        await self._refresh_queue()

    @rx.event
    async def set_cost_center(self, value: str) -> None:
        """Store the cost-center filter and re-project."""

        self.cost_center_filter = value
        await self._refresh_queue()

    @rx.event
    async def reset_filters(self) -> None:
        """Clear every filter and re-project."""

        self.search_text = ""
        self.status_filter = ""
        self.family_filter = ""
        self.cost_center_filter = ""
        await self._refresh_queue()

    @rx.event
    def open_detail(self, number: str) -> EventSpec:

        return rx.redirect(f"/requests/{number}")

    @rx.event
    async def load_detail(self) -> None:
        """Populate detail projections for the number in the URL path.

        No pagination by design (session-scale data; spec decision 14).
        """

        number = self.router.url.path.removeprefix("/requests").strip("/")
        self.not_found = False
        self.selected_number = number
        if not number:
            self.not_found = True
            return
        parent = await self.get_state(RequestCreateState)
        models = parent._submitted_models()
        try:
            request = get_request(models, number=number, viewer=REQUESTER_PROTOTYPE)
        except RequestNotFoundError:
            # Includes foreign-scope lookups: the UI presentation collapses
            # both to not-found so other users' numbers are not confirmable.
            self.not_found = True
            return
        except PermissionError:
            self.not_found = True
            return

        state = request.lifecycle_state
        payee = request.beneficiary.display_name
        details = request.details
        subtype = getattr(details, "subtype", None)
        type_label = request.request_type.value
        purpose = request.purpose
        created = request.created_at
        net = getattr(details, "invoice_net_amount", None) or getattr(
            details, "claimed_amount", None
        )
        vat = getattr(details, "vat_amount", None)
        gross = request.total_amount

        self.detail = {
            "number": request.request_number or number,
            "payee": payee,
            "purpose": purpose or "\u2014",
            "state": state.value,
            "tone": _TONE_BY_STATE[state],
            "overdue": "Overdue" if is_overdue(request, today=date.today()) else "",
            "breadcrumb_meta": (
                f"{type_label} \u00b7 {subtype.value}" if subtype is not None else type_label
            ),
            "requester": request.requester.display_name,
            "currency": request.total_amount.currency_code,
            "created_display": _fmt_date(created),
        }
        self.detail_amount = {
            "value": format_money(request.total_amount),
            "currency": request.total_amount.currency_code,
            "note": _AMOUNT_NOTE,
            "wave_label": f"Amount waveform for {format_money(request.total_amount)}",
        }
        self.stepper = _stepper_rows(state)
        tax_ref = request.beneficiary.tax_or_employee_reference or ""
        bank = request.beneficiary.bank_reference
        self.parties_rows = [
            _kv("Requester", request.requester.display_name),
            _kv("Payee", payee),
            _kv("Tax / employee ref", tax_ref),
            _kv(
                "Bank",
                f"{bank.bank_name} \u00b7 {bank.masked_account}" if bank else "",
            ),
            _kv(
                "Merchant / payee",
                getattr(details, "merchant_or_payee", "") or "",
            ),
        ]
        dims = request.accounting_dimension
        project = f"{dims.project_code} \u00b7 {dims.project_name}" if dims.project_code else ""
        self.accounting_rows = [
            _kv("Legal entity", f"{dims.legal_entity_code} \u00b7 {dims.legal_entity_name}"),
            _kv("Cost center", f"{dims.cost_center_code} \u00b7 {dims.cost_center_name}"),
            _kv("Project", project),
            _kv("Classification", dims.classification.value),
            _kv("Expense category", dims.expense_category_name),
            _kv("Budget period", dims.budget_period),
        ]
        self.amount_rows = [
            _kv("Net", format_money(net) if net else ""),
            _kv("VAT", format_money(vat) if vat else ""),
            _kv("Gross", format_money(gross)),
        ]
        # Honest empties: document persistence and workflow routing land in
        # later slices (approval-workflow effort); nothing is fabricated.
        self.doc_rows = [{"note": "No documents recorded on the submitted version."}]
        self.route_steps = []
        trail = parent._trail()
        events = events_for_request(trail.events(), request_id=request.request_id)
        self.audit_rows = [
            {
                "when": _fmt_datetime(event.occurred_at),
                "actor": event.actor.display_name,
                "action": event.action.value,
                "reason": event.reason or "",
            }
            for event in events
        ]
        self.audit_count = len(events)
        self.chain_verified = trail.verify()
