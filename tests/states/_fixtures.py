"""Shared fixture builders for state-helper unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from WisPay.models import (
    AccountingDimension,
    BeneficiaryReference,
    BeneficiaryType,
    LifecycleState,
    Money,
    PaymentRequest,
    RequestType,
    UserSnapshot,
    VendorPaymentDetails,
)
from WisPay.models.enums import OpexCapexClassification
from WisPay.services.request_query import RequestQueueRow
from WisPay.services.workflow_rules import SAMPLE_APPROVER_LINE_MANAGER, WorkflowRule


def make_money(amount: str = "10000000", currency: str = "VND") -> Money:
    """Build a standard Money value object."""
    return Money(amount=Decimal(amount), currency_code=currency, decimal_scale=0)


def _now() -> datetime:
    return datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def make_user_snapshot(identity: str = "entra-prototype-requester") -> UserSnapshot:
    """Build a standard UserSnapshot."""
    return UserSnapshot(
        external_identity_id=identity,
        display_name=identity,
        email=f"{identity}@wispay.example",
        captured_at=_now(),
    )


def make_vendor_request(
    *,
    state: LifecycleState = LifecycleState.SUBMITTED,
    number: str | None = "WPR-2026-0001",
    cost_center_code: str = "CC-100",
    total_amount: Money | None = None,
) -> PaymentRequest:
    """Build a PaymentRequest with vendor details for state helper tests."""

    gross = total_amount or make_money("10000000")
    zero = make_money("0")
    requester = make_user_snapshot()
    return PaymentRequest(
        request_id=uuid4(),
        request_number=number if number else None,
        submitted_version=None if not number else 1,
        request_type=RequestType.VENDOR,
        requester=requester,
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="Acme Corp",
            captured_at=_now(),
        ),
        accounting_dimension=AccountingDimension(
            legal_entity_code="VN01",
            legal_entity_name="WisPay Vietnam",
            department_code="FIN",
            department_name="Finance",
            cost_center_code=cost_center_code,
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
        details=VendorPaymentDetails(
            invoice_number=f"INV-{number[-4:]}" if number else "INV-0001",
            invoice_date=_now().date(),
            due_date=_now().date(),
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


def make_queue_row(
    *,
    state: LifecycleState = LifecycleState.SUBMITTED,
    number: str = "WPR-2026-0001",
    payee_display: str = "Acme Corp",
    type_label: str = "Vendor",
    subtype_label: str = "standard",
    amount: Money | None = None,
    submitted_at: datetime | None = None,
    overdue: bool = False,
) -> RequestQueueRow:
    """Build a RequestQueueRow fixture for state helper tests."""

    return RequestQueueRow(
        request_id=UUID("00000000-0000-4000-8000-000000000001"),
        number=number,
        payee_display=payee_display,
        type_label=type_label,
        subtype_label=subtype_label,
        amount=amount or make_money("10000000"),
        state=state,
        overdue=overdue,
        submitted_at=submitted_at or _now(),
    )


def make_workflow_rule(
    *,
    version: str = "v1",
    approver_role: str = "Line Manager",
    min_amount: Decimal | None = None,
    step_sequence: int = 1,
    currency_code: str | None = "VND",
) -> WorkflowRule:
    """Build a WorkflowRule fixture for admin_state tests."""

    from WisPay.models.enums import RoleName

    return WorkflowRule(
        version=version,
        priority=10,
        request_type=None,
        min_amount=min_amount,
        currency_code=currency_code,
        legal_entity_code=None,
        department_code=None,
        project_code=None,
        risk_flag=None,
        step_sequence=step_sequence,
        parallel_group=None,
        approver_role=RoleName(approver_role),
        approver_user=SAMPLE_APPROVER_LINE_MANAGER,
        due_days=3,
    )
