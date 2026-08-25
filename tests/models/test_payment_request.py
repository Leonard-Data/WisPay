from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from WisPay.models import (
    AccountingDimension,
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

NOW = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)


def money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def user() -> UserSnapshot:
    return UserSnapshot(
        external_identity_id="entra-user-1",
        display_name="Nguyen An",
        email="an@example.com",
        department="Finance",
        captured_at=NOW,
    )


def beneficiary() -> BeneficiaryReference:
    return BeneficiaryReference(
        beneficiary_type=BeneficiaryType.VENDOR,
        external_master_data_id="V-001",
        display_name="Example Vendor",
        tax_or_employee_reference="TAX-001",
        captured_at=NOW,
    )


def accounting_dimension() -> AccountingDimension:
    return AccountingDimension(
        legal_entity_code="VN01",
        legal_entity_name="WisPay Vietnam",
        department_code="FIN",
        department_name="Finance",
        cost_center_code="CC-100",
        cost_center_name="Corporate Finance",
        expense_category_code="SERVICES",
        expense_category_name="Professional Services",
        classification=OpexCapexClassification.OPEX,
        budget_period="2026-01",
        captured_at=NOW,
    )


def vendor_details() -> VendorPaymentDetails:
    return VendorPaymentDetails(
        invoice_number="INV-001",
        invoice_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        invoice_net_amount=money("100000"),
        vat_amount=money("10000"),
        invoice_gross_amount=money("110000"),
        payment_terms="Net 30",
        proposed_payment_method="Bank transfer",
        duplicate_warning_key="V-001|INV-001|110000|2026-01-01",
    )


def draft_request() -> PaymentRequest:
    return PaymentRequest(
        request_id=uuid4(),
        request_type=RequestType.VENDOR,
        requester=user(),
        beneficiary=beneficiary(),
        accounting_dimension=accounting_dimension(),
        purpose="January professional services",
        total_amount=money("110000"),
        accounting_period="2026-01",
        lifecycle_version="ADR-0006-v1",
        details=vendor_details(),
        created_at=NOW,
        updated_at=NOW,
    )


def test_draft_request_is_frozen_and_supports_functional_updates() -> None:
    request = draft_request()

    with pytest.raises(ValidationError, match="frozen"):
        request.purpose = "Changed in place"

    submitted = request.evolve(
        request_number="PR-2026-000001",
        submitted_version=1,
        lifecycle_state=LifecycleState.SUBMITTED,
    )

    assert request.lifecycle_state is LifecycleState.DRAFT
    assert submitted.lifecycle_state is LifecycleState.SUBMITTED
    assert submitted.request_number == "PR-2026-000001"

    with pytest.raises(ValidationError, match="request number"):
        request.evolve(lifecycle_state=LifecycleState.SUBMITTED)


def test_submitted_request_requires_number_and_version() -> None:
    data = draft_request().model_dump()
    data["lifecycle_state"] = LifecycleState.SUBMITTED

    with pytest.raises(ValidationError, match="request number"):
        PaymentRequest.model_validate(data)


def test_request_type_must_match_discriminated_details() -> None:
    data = draft_request().model_dump()
    data["request_type"] = RequestType.EMPLOYEE

    with pytest.raises(ValidationError, match="request_type"):
        PaymentRequest.model_validate(data)


def test_request_total_must_match_type_specific_amount() -> None:
    data = draft_request().model_dump()
    data["total_amount"] = money("120000")

    with pytest.raises(ValidationError, match="total_amount"):
        PaymentRequest.model_validate(data)


def test_vendor_invoice_amounts_must_balance() -> None:
    data = vendor_details().model_dump()
    data["invoice_gross_amount"] = money("120000")

    with pytest.raises(ValidationError, match="gross"):
        VendorPaymentDetails.model_validate(data)
