"""Create-wizard state adapter for ``/requests/new``.

Thin UI adapter per ADR-0005: every business rule lives in
``WisPay.services.request_creation`` / ``audit_trail``; this class only
sequences calls, holds form values, and translates typed outcomes into
renderable vars.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import reflex as rx
from pydantic import ValidationError as PydanticValidationError

from states.auth_state import AuthState
from WisPay.models import PaymentRequest  # noqa: TC001 - needed for Reflex hints
from WisPay.services.audit_trail import InMemoryAuditTrail
from WisPay.services.reference_data import (
    REQUESTER_PROTOTYPE,
    doc_requirements,
)
from WisPay.services.request_creation import (
    DraftCommand,
    build_payment_request,
    duplicate_scan,
    parse_money,
    submit_request,
    validate_draft_command,
)

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".xlsx"})
_TEXT_FIELDS = (
    "family",
    "subtype",
    "title",
    "purpose",
    "currency",
    "net_text",
    "vat_text",
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "payment_terms_code",
    "payment_method_code",
    "merchant",
    "expense_date",
    "policy_category",
    "activity_start",
    "activity_end",
    "requested_payment_date",
    "linked_advance_id",
    "legal_entity",
    "cost_center",
    "project",
    "expense_category",
    "classification",
    "budget_period",
)


def _normalize_input(value: str | int | float) -> str:
    """Coerce widget input to a clean string without float artifacts."""

    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return value


def _format_amount(value: Decimal, currency: str) -> str:
    quantized = value.quantize(Decimal("0.01")) if currency.upper() != "VND" else value
    digits = f"{quantized:,.2f}" if currency.upper() != "VND" else f"{quantized:,.0f}"
    return f"{digits} {currency.upper()}"


class RequestCreateState(AuthState):
    """Wizard draft, validation outcomes, and session submission store."""

    # Wizard position and selection
    step: int = 1
    family: str = ""
    subtype: str = ""

    # Shared detail fields
    title: str = ""
    purpose: str = ""
    currency: str = "VND"
    net_text: str = ""
    vat_text: str = ""

    # Vendor fields
    vendor_name: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    due_date: str = ""
    payment_terms_code: str = ""
    payment_method_code: str = ""

    # Employee fields
    merchant: str = ""
    expense_date: str = ""
    policy_category: str = ""
    activity_start: str = ""
    activity_end: str = ""
    requested_payment_date: str = ""
    linked_advance_id: str = ""

    # Accounting fields
    legal_entity: str = ""
    cost_center: str = ""
    project: str = ""
    expense_category: str = ""
    classification: str = "OPEX"
    budget_period: str = ""

    # Outcomes and uploads
    field_errors: dict[str, str] = {}
    blocking: list[str] = []
    warnings: list[str] = []
    uploads: list[dict[str, Any]] = []
    upload_errors: dict[str, str] = {}

    # Result surfaces
    submitted_number: str = ""
    gross_preview: str = ""
    status_message: str = ""

    # Session submission store (queue/summary consumers; models kept privately)
    submitted_requests: list[dict[str, Any]] = []

    # Backend-only session objects (underscore vars are not synced to the UI).
    _session_trail: InMemoryAuditTrail | None = None
    _submitted_model_store: list[PaymentRequest] | None = None

    def _trail(self) -> InMemoryAuditTrail:
        """Return this session's audit trail, creating it on first submit."""

        if self._session_trail is None:
            self._session_trail = InMemoryAuditTrail()
        assert self._session_trail is not None
        return self._session_trail

    def _submitted_models(self) -> list[PaymentRequest]:
        """Submitted aggregates for duplicate scanning and settlement links."""

        if self._submitted_model_store is None:
            self._submitted_model_store = []
        assert self._submitted_model_store is not None
        return self._submitted_model_store

    def _command(self) -> DraftCommand:
        return DraftCommand(**{name: getattr(self, name) for name in _TEXT_FIELDS})

    def _uploaded_keys(self) -> frozenset[str]:
        return frozenset(str(entry.get("key")) for entry in self.uploads)

    def _recalc_gross(self) -> None:
        try:
            net = parse_money(self.net_text, self.currency)
            if self.family == "employee":
                self.gross_preview = _format_amount(net.amount, self.currency)
                return
            vat = parse_money(self.vat_text, self.currency) if self.vat_text.strip() else None
            total = net + vat if vat is not None else net
            self.gross_preview = _format_amount(total.amount, self.currency)
        except ValueError:
            self.gross_preview = ""

    @rx.event
    def select_type(self, family: str, subtype: str) -> None:
        """Choose a request type card; clears stale errors."""

        self.family = family
        self.subtype = subtype
        self.field_errors = {}
        self.blocking = []
        self.status_message = ""
        if subtype == "settlement":
            self.vat_text = ""
        if not self.budget_period:
            self.budget_period = datetime.now(UTC).strftime("%Y-%m")
        self._recalc_gross()

    @rx.event
    def set_field(self, name: str, value: str | int | float) -> None:
        """Update one whitelisted text field and refresh derived amounts.

        ``type="number"`` inputs deliver numbers; normalize to plain strings
        so Decimal parsing never sees float artifacts like ``"1e7"``.
        """

        if name not in _TEXT_FIELDS:
            return
        text = _normalize_input(value)
        setattr(self, name, text)
        if name == "linked_advance_id" and text:
            advance = next(
                (entry for entry in self.submitted_requests if entry.get("request_id") == text),
                None,
            )
            if advance is not None and not self.title:
                self.title = f"Settlement of {advance.get('number', 'advance')}"
        errors = dict(self.field_errors)
        errors.pop(name, None)
        self.field_errors = errors
        if name in ("net_text", "vat_text", "currency"):
            self._recalc_gross()

    @rx.event
    def recalc_gross(self) -> None:
        """Recompute the gross amount preview."""

        self._recalc_gross()

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]) -> None:
        """Capture files into session metadata with type/size/checksum rules."""

        for file in files:
            filename = file.filename or "upload"
            extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            slot_error = ""
            if extension not in _ALLOWED_UPLOAD_EXTENSIONS:
                slot_error = "Choose a PDF, PNG, JPG, or XLSX file."
            data = b""
            if not slot_error:
                data = await file.read()
                size = file.size if file.size is not None else len(data)
                if size > _MAX_UPLOAD_BYTES:
                    slot_error = "This file is larger than 10 MB."
            pending = [
                requirement.key
                for requirement in doc_requirements(self.family, self.subtype)
                if requirement.key not in self._uploaded_keys()
            ]
            key = pending[0] if pending else "extra"
            errors = dict(self.upload_errors)
            if slot_error:
                errors[key] = slot_error
                self.upload_errors = errors
                continue
            errors.pop(key, None)
            self.upload_errors = errors
            self.uploads = [
                *self.uploads,
                {
                    "key": key,
                    "file_name": filename,
                    "size_bytes": len(data),
                    "sha256_hex": hashlib.sha256(data).hexdigest(),
                },
            ]

    @rx.event
    def remove_upload(self, key: str) -> None:
        """Detach an uploaded document slot."""

        self.uploads = [entry for entry in self.uploads if entry.get("key") != key]

    def _validate_details(self) -> bool:
        """Run full validation; store both error classes for later steps.

        Returns whether *field* issues are clear — document blockers are
        surfaced at the Documents gate and Review, never here.
        """

        outcome = validate_draft_command(self._command(), self._uploaded_keys())
        self.field_errors = {issue.field: issue.message for issue in outcome.field_issues}
        self.blocking = list(outcome.blocking)
        return not outcome.field_issues

    @rx.event
    def go_next(self) -> None:
        """Advance one gated step: type chosen, details valid, docs satisfied."""

        if self.step == 1:
            if not self.family:
                self.status_message = "Select a request type first."
                return
        elif self.step == 2 and not self._validate_details():
            self.status_message = "Request details need attention."
            return
        elif self.step == 3:
            missing = [
                f"Attach {requirement.label}."
                for requirement in doc_requirements(self.family, self.subtype)
                if requirement.required and requirement.key not in self._uploaded_keys()
            ]
            self.blocking = missing
            if missing:
                self.status_message = "Attach the required documents before continuing."
                return
            self.warnings = list(duplicate_scan(self._submitted_models(), self._command()))
        self.step += 1

    @rx.event
    def go_back(self) -> None:
        """Step back one panel, clearing gate messages."""

        self.status_message = ""
        if self.step > 1:
            self.step -= 1

    @rx.event
    def go_to_step(self, target: int) -> None:
        """Jump back to an already-completed step."""

        self.status_message = ""
        if 1 <= target < self.step:
            self.step = target

    @rx.event
    def submit(self) -> None:
        """Validate, build, submit, and audit-log the request in one action."""

        if self.submitted_number:
            return
        if not self._validate_details():
            self.status_message = "Resolve the blocking issues before submitting."
            return
        now = datetime.now(UTC)
        try:
            draft = build_payment_request(self._command(), requester=REQUESTER_PROTOTYPE, now=now)
        except PydanticValidationError as error:
            errors = dict(self.field_errors)
            for issue in error.errors():
                loc = str(issue.get("loc", ("",))[0])
                if loc:
                    errors.setdefault(loc, str(issue.get("msg", "Invalid value.")))
            self.field_errors = errors
            self.status_message = "Resolve the blocking issues before submitting."
            return
        sequence = len(self.submitted_requests) + 1
        number = f"WPR-{now.year}-{sequence:04d}"
        try:
            result = submit_request(
                draft,
                actor=REQUESTER_PROTOTYPE,
                now=now,
                request_number=number,
                trail=self._trail(),
            )
        except ValueError as error:
            self.status_message = str(error)
            return
        self.warnings = list(duplicate_scan(self._submitted_models(), self._command()))
        self._submitted_models().append(result.request)
        try:
            from WisPay.services.runtime import stores

            stores().requests.save(result.request)
        except Exception:  # noqa: BLE001 - durability is best-effort this iteration
            self.status_message = (
                "Request submitted in this session; durable storage is unreachable, "
                "so it will not appear in approval tracking."
            )
        self.submitted_requests = [
            *self.submitted_requests,
            {
                "request_id": str(result.request.request_id),
                "number": result.request.request_number or number,
                "title": self.title,
                "family": self.family,
                "subtype": self.subtype,
                "total": str(result.request.total_amount.amount),
                "currency": result.request.total_amount.currency_code,
                "state": result.request.lifecycle_state.value,
                "submitted_at": now.isoformat(),
            },
        ]
        self.submitted_number = result.request.request_number or number

    @rx.var(cache=True)
    def settleable_advances(self) -> list[dict[str, str]]:
        """Submitted cash advances from this session eligible for settlement."""

        return [
            {
                "request_id": str(entry.get("request_id")),
                "number": str(entry.get("number")),
                "title": str(entry.get("title")),
            }
            for entry in self.submitted_requests
            if entry.get("family") == "employee" and entry.get("subtype") == "advance"
        ]

    @rx.var(cache=True)
    def field_issue_rows(self) -> list[dict[str, str]]:
        """Field issues as rows so review can list them with foreach."""

        return [
            {"field": field, "message": message}
            for field, message in sorted(self.field_errors.items())
        ]

    @rx.var(cache=True)
    def doc_rows(self) -> list[dict[str, Any]]:
        """Document checklist rows for the current type selection."""

        return [
            {"key": requirement.key, "label": requirement.label, "required": requirement.required}
            for requirement in doc_requirements(self.family, self.subtype)
        ]

    @rx.var(cache=True)
    def doc_keys(self) -> list[str]:
        """Slot keys required/optional for the current type selection."""

        return [requirement.key for requirement in doc_requirements(self.family, self.subtype)]

    @rx.var(cache=True)
    def required_doc_keys(self) -> list[str]:
        """Slot keys that block submission until attached."""

        return [
            requirement.key
            for requirement in doc_requirements(self.family, self.subtype)
            if requirement.required
        ]

    @rx.var(cache=True)
    def uploaded_keys(self) -> list[str]:
        """Slot keys already satisfied by an attachment."""

        return [str(entry.get("key")) for entry in self.uploads]

    @rx.var(cache=True)
    def issue_count(self) -> int:
        """Number of open blocking issues surfaced at review."""

        return len(self.field_errors) + len(self.blocking)

    @rx.var(cache=True)
    def error_fields(self) -> list[str]:
        """Field names currently invalid; drives per-field error rendering."""

        return sorted(self.field_errors)

    @rx.var(cache=True)
    def payee_display(self) -> str:
        """Beneficiary for the review summary: vendor name, or the prototype employee."""

        if self.family == "vendor":
            return self.vendor_name
        if self.family == "employee":
            return REQUESTER_PROTOTYPE.display_name
        return ""

    @rx.var(cache=True)
    def accounting_period(self) -> str:
        """YYYY-MM preview mirroring the service's accounting-period rule."""

        source = (
            self.invoice_date
            if self.family == "vendor"
            else (self.activity_start or self.expense_date)
        )
        if len(source) >= 7:
            return source[:7]
        return datetime.now(tz=UTC).strftime("%Y-%m")

    @rx.event
    def reset_wizard(self) -> None:
        """Restore pristine wizard defaults; session history is retained."""

        for name in _TEXT_FIELDS:
            setattr(self, name, "")
        self.step = 1
        self.classification = "OPEX"
        self.currency = "VND"
        self.field_errors = {}
        self.blocking = []
        self.warnings = []
        self.uploads = []
        self.upload_errors = {}
        self.gross_preview = ""
        self.status_message = ""
        self.submitted_number = ""
