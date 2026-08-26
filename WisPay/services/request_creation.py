"""Payment Request draft validation, construction, and submission.

Pure-domain service for the create wizard (spec: ``.scratch/payment-request-create``).
Owns every business rule; Reflex state only sequences calls and translates typed
outcomes into UI vars (ADR-0005). No Reflex import may appear in this module.

Amounts arrive as raw decimal strings from the wizard and are parsed into
:class:`~WisPay.models.money.Money` values — floats are prohibited domain-wide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Sequence

from WisPay.models import (
    AccountingDimension,
    AuditAction,
    AuditEvent,
    BeneficiaryReference,
    BeneficiaryType,
    EmployeePaymentDetails,
    EmployeeRequestSubtype,
    LifecycleState,
    Money,
    PaymentRequest,
    RequestType,
    UserSnapshot,
    VendorPaymentDetails,
    WisPayBaseModel,
)
from WisPay.services.reference_data import (
    COST_CENTERS,
    CURRENCIES,
    EXPENSE_CATEGORIES,
    LEGAL_ENTITIES,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    POLICY_CATEGORIES,
    RETENTION_POLICY_ID_PROTOTYPE,
    doc_requirements,
)

if TYPE_CHECKING:
    from WisPay.services.audit_trail import InMemoryAuditTrail

_LIFECYCLE_VERSION = "v1"
_SUBTYPES_BY_KEY: dict[str, EmployeeRequestSubtype] = {
    "reimbursement": EmployeeRequestSubtype.REIMBURSEMENT,
    "advance": EmployeeRequestSubtype.ADVANCE,
    "settlement": EmployeeRequestSubtype.ADVANCE_SETTLEMENT,
    "internal": EmployeeRequestSubtype.INTERNAL_EXPENDITURE,
}
_CLASSIFICATIONS: frozenset[str] = frozenset({"OPEX", "CAPEX"})
_AMOUNT_CHARS = frozenset("0123456789.")


class DraftCommand(WisPayBaseModel):
    """Every raw wizard input, typed but unparsed.

    Field names mirror ``RequestCreateState`` vars one-to-one so field issues
    bind straight onto form controls.
    """

    family: str = ""
    subtype: str = ""
    title: str = ""
    purpose: str = ""
    currency: str = "VND"
    net_text: str = ""
    vat_text: str = ""
    vendor_name: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    due_date: str = ""
    payment_terms_code: str = ""
    payment_method_code: str = ""
    merchant: str = ""
    expense_date: str = ""
    policy_category: str = ""
    activity_start: str = ""
    activity_end: str = ""
    requested_payment_date: str = ""
    linked_advance_id: str = ""
    legal_entity: str = ""
    cost_center: str = ""
    project: str = ""
    expense_category: str = ""
    classification: str = ""
    budget_period: str = ""


class FieldIssue(WisPayBaseModel):
    """One invalid field: ``field`` equals the wizard state var name."""

    field: str
    message: str


class ValidationOutcome(WisPayBaseModel):
    """Typed result of cheap pre-model validation."""

    field_issues: tuple[FieldIssue, ...] = ()
    blocking: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.field_issues and not self.blocking


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    """Submitted aggregate plus the audit event that records the action."""

    request: PaymentRequest
    audit_event: AuditEvent


def _currency_scale(currency: str) -> int:
    code = currency.strip().upper()
    for supported, scale in CURRENCIES:
        if supported == code:
            return scale
    raise ValueError("Select a supported currency (VND, USD, or EUR).")


def parse_money(text: str, currency: str) -> Money:
    """Parse a wizard amount string into ``Money`` with user-safe errors."""

    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Enter an amount greater than zero.")
    if any(char not in _AMOUNT_CHARS for char in cleaned) or cleaned.count(".") > 1:
        raise ValueError("Enter a valid number, digits only.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as error:
        raise ValueError("Enter a valid number, digits only.") from error
    if amount <= 0:
        raise ValueError("Enter an amount greater than zero.")
    scale = _currency_scale(currency)
    quantum = Decimal(1).scaleb(-scale)
    if amount != amount.quantize(quantum):
        if currency.strip().upper() == "VND":
            raise ValueError("VND amounts cannot use decimal places.")
        raise ValueError(f"Use at most {scale} decimal places for {currency.upper()}.")
    return Money(amount=amount, currency_code=currency.strip().upper(), decimal_scale=scale)


def gross_of(net: Money, vat: Money) -> Money:
    """Return net plus VAT; both values must share currency and scale."""

    return net + vat


def _try_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def validate_draft_command(
    cmd: DraftCommand,
    uploaded_keys: frozenset[str] = frozenset(),
) -> ValidationOutcome:
    """Validate raw wizard input per family without constructing models.

    Field issues use state-var names so the UI can bind errors generically;
    document gaps are blocking messages because they gate submission itself.
    """

    issues: list[FieldIssue] = []
    blocking: list[str] = []

    def issue(field: str, message: str) -> None:
        issues.append(FieldIssue(field=field, message=message))

    def require_iso_date(field: str, label: str) -> date | None:
        parsed = _try_iso_date(getattr(cmd, field))
        if parsed is None:
            issue(field, f"Select {label}.")
        return parsed

    if cmd.family not in ("vendor", "employee"):
        issue("family", "Choose a request type first.")
        return ValidationOutcome(field_issues=tuple(issues))

    if not cmd.title.strip():
        issue("title", "Add a clear request title.")
    if not cmd.purpose.strip():
        issue("purpose", "Explain the business purpose.")

    try:
        parse_money(cmd.net_text, cmd.currency)
    except ValueError as error:
        issue("net_text", str(error))
    if cmd.vat_text.strip():
        try:
            parse_money(cmd.vat_text, cmd.currency)
        except ValueError as error:
            issue("vat_text", str(error))

    accounting_date: date | None = None
    if cmd.family == "vendor":
        if not cmd.vendor_name.strip():
            issue("vendor_name", "Enter the vendor being paid.")
        if not cmd.invoice_number.strip():
            issue("invoice_number", "Enter the vendor invoice number.")
        invoice_date = require_iso_date("invoice_date", "the invoice date")
        due_date = require_iso_date("due_date", "the payment due date")
        if invoice_date is not None and due_date is not None and due_date < invoice_date:
            issue("due_date", "The due date must be on or after the invoice date.")
        accounting_date = invoice_date
        if not cmd.payment_terms_code:
            issue("payment_terms_code", "Select the agreed payment terms.")
        elif cmd.payment_terms_code not in {option.code for option in PAYMENT_TERMS}:
            issue("payment_terms_code", "Select payment terms from the list.")
        if not cmd.payment_method_code:
            issue("payment_method_code", "Select the proposed payment method.")
        elif cmd.payment_method_code not in {option.code for option in PAYMENT_METHODS}:
            issue("payment_method_code", "Select a payment method from the list.")
    else:
        subtype_key = cmd.subtype.strip().lower()
        if subtype_key not in _SUBTYPES_BY_KEY:
            issue("subtype", "Choose an employee request subtype.")
        if subtype_key == "reimbursement":
            if not cmd.merchant.strip():
                issue("merchant", "Enter the merchant or payee name.")
            accounting_date = require_iso_date("expense_date", "the expense date")
        elif subtype_key == "advance":
            start = require_iso_date("activity_start", "the activity start date")
            end = require_iso_date("activity_end", "the activity end date")
            if start is not None and end is not None and end < start:
                issue("activity_end", "Activity end must be on or after the start date.")
            accounting_date = start
        elif subtype_key == "settlement":
            if not cmd.linked_advance_id.strip():
                issue("linked_advance_id", "Select the advance this request settles.")
            else:
                try:
                    UUID(cmd.linked_advance_id)
                except ValueError:
                    issue("linked_advance_id", "Select a submitted advance from the list.")
        if subtype_key in ("reimbursement", "internal") and not cmd.policy_category:
            issue("policy_category", "Select an expense category.")
        elif (
            subtype_key in ("reimbursement", "internal")
            and cmd.policy_category not in POLICY_CATEGORIES
        ):
            issue("policy_category", "Select a category from the list.")
        requested = require_iso_date("requested_payment_date", "the requested payment date")
        if accounting_date is None:
            accounting_date = requested

    entity_codes = {option.code for option in LEGAL_ENTITIES}
    center_codes = {option.code for option in COST_CENTERS}
    category_codes = {option.code for option in EXPENSE_CATEGORIES}
    if cmd.legal_entity not in entity_codes:
        issue("legal_entity", "Select the legal entity.")
    if cmd.cost_center not in center_codes:
        issue("cost_center", "Select the cost center that owns this spend.")
    if cmd.expense_category not in category_codes:
        issue("expense_category", "Select an expense category.")
    if cmd.classification not in _CLASSIFICATIONS:
        issue("classification", "Choose OPEX or CAPEX.")
    period = cmd.budget_period.strip()
    valid_period = (
        len(period) == 7 and period[:4].isdigit() and period[5:].isdigit() and period[4] == "-"
    )
    if not valid_period:
        issue("budget_period", "Pick the budget month (YYYY-MM).")

    for requirement in doc_requirements(cmd.family, cmd.subtype):
        if requirement.required and requirement.key not in uploaded_keys:
            blocking.append(f"Attach {requirement.label}.")

    return ValidationOutcome(
        field_issues=tuple(issues),
        blocking=tuple(blocking),
        warnings=(),
    )


def build_payment_request(
    cmd: DraftCommand,
    *,
    requester: UserSnapshot,
    now: datetime,
) -> PaymentRequest:
    """Construct a validated DRAFT aggregate from wizard input.

    Raises :class:`pydantic.ValidationError` when any model invariant fails;
    callers run :func:`validate_draft_command` first for friendly messages.
    """

    net = parse_money(cmd.net_text, cmd.currency)
    vat = parse_money(cmd.vat_text, cmd.currency) if cmd.vat_text.strip() else None
    entity = next(option for option in LEGAL_ENTITIES if option.code == cmd.legal_entity)
    center = next(option for option in COST_CENTERS if option.code == cmd.cost_center)
    category = next(option for option in EXPENSE_CATEGORIES if option.code == cmd.expense_category)

    if cmd.family == "vendor":
        invoice_date = date.fromisoformat(cmd.invoice_date)
        terms = next(
            option.name for option in PAYMENT_TERMS if option.code == cmd.payment_terms_code
        )
        method = next(
            option.name for option in PAYMENT_METHODS if option.code == cmd.payment_method_code
        )
        gross = gross_of(net, vat) if vat is not None else net
        zero_vat = Money(
            amount=Decimal(0), currency_code=gross.currency_code, decimal_scale=gross.decimal_scale
        )
        details: VendorPaymentDetails | EmployeePaymentDetails = VendorPaymentDetails(
            invoice_number=cmd.invoice_number.strip(),
            invoice_date=invoice_date,
            due_date=date.fromisoformat(cmd.due_date),
            invoice_net_amount=net,
            vat_amount=vat if vat is not None else zero_vat,
            invoice_gross_amount=gross,
            payment_terms=terms,
            proposed_payment_method=method,
            duplicate_warning_key=(
                f"{cmd.vendor_name.casefold()}|{cmd.invoice_number.strip()}|{gross.amount}"
            ),
        )
        beneficiary_type = BeneficiaryType.VENDOR
        display_name = cmd.vendor_name.strip()
        total = gross
        period_source = invoice_date
    else:
        subtype = _SUBTYPES_BY_KEY[cmd.subtype.strip().lower()]
        activity_start = (
            _try_iso_date(cmd.activity_start) or _try_iso_date(cmd.expense_date) or date.today()
        )
        details = EmployeePaymentDetails(
            subtype=subtype,
            employee=requester,
            policy_category=cmd.policy_category,
            activity_start_date=activity_start,
            activity_end_date=(_try_iso_date(cmd.activity_end) or activity_start),
            merchant_or_payee=cmd.merchant or None,
            claimed_amount=net,
            vat_amount=vat,
            requested_payment_date=date.fromisoformat(cmd.requested_payment_date),
            related_advance_request_id=(
                UUID(cmd.linked_advance_id) if cmd.linked_advance_id.strip() else None
            ),
        )
        beneficiary_type = BeneficiaryType.EMPLOYEE
        display_name = requester.display_name
        total = net
        period_source = activity_start

    dimension = AccountingDimension(
        legal_entity_code=entity.code,
        legal_entity_name=entity.name,
        department_code=center.code,
        department_name=center.name,
        cost_center_code=center.code,
        cost_center_name=center.name,
        project_code=cmd.project or None,
        project_name=cmd.project or None,
        expense_category_code=category.code,
        expense_category_name=category.name,
        classification=cmd.classification,  # type: ignore[arg-type]
        budget_period=cmd.budget_period,
        captured_at=now,
    )
    return PaymentRequest(
        request_id=uuid4(),
        request_type=RequestType.VENDOR if cmd.family == "vendor" else RequestType.EMPLOYEE,
        requester=requester,
        beneficiary=BeneficiaryReference(
            beneficiary_type=beneficiary_type,
            display_name=display_name,
            captured_at=now,
        ),
        accounting_dimension=dimension,
        purpose=cmd.purpose,
        total_amount=total,
        accounting_period=f"{period_source.year:04d}-{period_source.month:02d}",
        lifecycle_version=_LIFECYCLE_VERSION,
        details=details,
        created_at=now,
        updated_at=now,
    )


def submit_request(
    req: PaymentRequest,
    *,
    actor: UserSnapshot,
    now: datetime,
    request_number: str,
    trail: InMemoryAuditTrail,
    retention_policy_id: UUID = RETENTION_POLICY_ID_PROTOTYPE,
) -> SubmissionResult:
    """Transition a DRAFT request to SUBMITTED and append its audit event.

    The lifecycle guard makes double submission impossible: a submitted
    aggregate no longer satisfies ``lifecycle_state is DRAFT``.
    """

    if req.lifecycle_state is not LifecycleState.DRAFT:
        raise ValueError("Only draft requests can be submitted.")
    submitted = req.evolve(
        request_number=request_number,
        submitted_version=1,
        lifecycle_state=LifecycleState.SUBMITTED,
        updated_at=now,
    )
    event = trail.append(
        entity_type="PaymentRequest",
        entity_id=str(submitted.request_id),
        actor=actor,
        action=AuditAction.SUBMITTED,
        occurred_at=submitted.updated_at,
        new_value=submitted.model_dump_json(round_trip=True),
        correlation_id=f"submit:{submitted.request_id}",
        retention_policy_id=retention_policy_id,
    )
    return SubmissionResult(request=submitted, audit_event=event)


def duplicate_scan(
    existing: Sequence[PaymentRequest],
    cmd: DraftCommand,
) -> tuple[str, ...]:
    """Return warnings for same-session vendor duplicates (name + invoice)."""

    if cmd.family != "vendor" or not cmd.vendor_name.strip() or not cmd.invoice_number.strip():
        return ()
    name = cmd.vendor_name.casefold()
    hits = [
        request
        for request in existing
        if request.request_type is RequestType.VENDOR
        and request.beneficiary.display_name.casefold() == name
        and isinstance(request.details, VendorPaymentDetails)
        and request.details.invoice_number == cmd.invoice_number.strip()
    ]
    if not hits:
        return ()
    count = len(hits)
    suffix = "" if count == 1 else "s"
    return (f"Possible duplicate: {count} request{suffix} use the same vendor and invoice number.",)
