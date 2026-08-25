from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import BeneficiaryType, EmployeeRequestSubtype, RequestType, SettlementStatus
from .lifecycle import LifecycleState
from .money import Money
from .references import AccountingDimension, BeneficiaryReference, UserSnapshot


class VendorPaymentDetails(WisPayBaseModel):
    request_type: Literal[RequestType.VENDOR] = RequestType.VENDOR
    invoice_number: NonEmptyStr
    invoice_date: date
    due_date: date
    invoice_net_amount: Money
    vat_amount: Money
    invoice_gross_amount: Money
    payment_terms: NonEmptyStr
    proposed_payment_method: NonEmptyStr
    purchase_order_reference: NonEmptyStr | None = None
    contract_reference: NonEmptyStr | None = None
    goods_receipt_reference: NonEmptyStr | None = None
    service_acceptance_reference: NonEmptyStr | None = None
    tax_identifier: NonEmptyStr | None = None
    duplicate_warning_key: NonEmptyStr
    non_po_exception_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_invoice_amounts(self) -> Self:
        if self.due_date < self.invoice_date:
            raise ValueError("invoice due_date must not precede invoice_date")
        amounts = (self.invoice_net_amount, self.vat_amount, self.invoice_gross_amount)
        if any(
            amount.currency_code != amounts[0].currency_code
            or amount.decimal_scale != amounts[0].decimal_scale
            for amount in amounts[1:]
        ):
            raise ValueError("invoice amounts must use the same currency and decimal scale")
        if self.invoice_net_amount + self.vat_amount != self.invoice_gross_amount:
            raise ValueError("invoice net amount plus VAT must equal gross amount")
        return self


class EmployeePaymentDetails(WisPayBaseModel):
    request_type: Literal[RequestType.EMPLOYEE] = RequestType.EMPLOYEE
    subtype: EmployeeRequestSubtype
    employee: UserSnapshot
    policy_category: NonEmptyStr
    activity_start_date: date
    activity_end_date: date
    merchant_or_payee: NonEmptyStr | None = None
    claimed_amount: Money
    vat_amount: Money | None = None
    requested_payment_date: date
    related_advance_request_id: UUID | None = None
    receipt_warning_key: NonEmptyStr | None = None
    missing_receipt_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_employee_details(self) -> Self:
        if self.activity_end_date < self.activity_start_date:
            raise ValueError("activity_end_date must not precede activity_start_date")
        if self.vat_amount is not None and (
            self.vat_amount.currency_code != self.claimed_amount.currency_code
            or self.vat_amount.decimal_scale != self.claimed_amount.decimal_scale
        ):
            raise ValueError("VAT must use the claimed amount currency and decimal scale")
        if (
            self.subtype is EmployeeRequestSubtype.ADVANCE_SETTLEMENT
            and self.related_advance_request_id is None
        ):
            raise ValueError("advance settlements must reference the original advance")
        return self


type PaymentDetails = Annotated[
    VendorPaymentDetails | EmployeePaymentDetails,
    Field(discriminator="request_type"),
]


class EmployeeAdvanceSettlement(WisPayBaseModel):
    settlement_request_id: UUID
    original_advance_request_id: UUID
    approved_advance_amount: Money
    actual_eligible_expense: Money
    returned_amount: Money
    additional_reimbursement: Money
    status: SettlementStatus

    @model_validator(mode="after")
    def validate_settlement_balance(self) -> Self:
        amounts = (
            self.approved_advance_amount,
            self.actual_eligible_expense,
            self.returned_amount,
            self.additional_reimbursement,
        )
        if any(
            amount.currency_code != amounts[0].currency_code
            or amount.decimal_scale != amounts[0].decimal_scale
            for amount in amounts[1:]
        ):
            raise ValueError("settlement amounts must share currency and decimal scale")
        if self.returned_amount.amount and self.additional_reimbursement.amount:
            raise ValueError("a settlement cannot require both a return and reimbursement")
        if (
            self.approved_advance_amount.amount + self.additional_reimbursement.amount
            != self.actual_eligible_expense.amount + self.returned_amount.amount
        ):
            raise ValueError("settlement amounts do not balance")
        return self


class PaymentRequest(WisPayBaseModel):
    request_id: UUID
    request_number: NonEmptyStr | None = None
    request_type: RequestType
    requester: UserSnapshot
    beneficiary: BeneficiaryReference
    accounting_dimension: AccountingDimension
    purpose: NonEmptyStr
    total_amount: Money
    accounting_period: NonEmptyStr
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    lifecycle_version: NonEmptyStr
    submitted_version: int | None = Field(default=None, ge=1)
    details: PaymentDetails
    supporting_document_ids: tuple[UUID, ...] = ()
    workflow_instance_id: UUID | None = None
    payment_record_ids: tuple[UUID, ...] = ()
    created_at: AwareDateTime
    updated_at: AwareDateTime

    @model_validator(mode="after")
    def validate_request_identity_and_type(self) -> Self:
        if self.request_type is not self.details.request_type:
            raise ValueError("request_type must match the type-specific details")
        expected_beneficiary_type = (
            BeneficiaryType.VENDOR
            if self.request_type is RequestType.VENDOR
            else BeneficiaryType.EMPLOYEE
        )
        if self.beneficiary.beneficiary_type is not expected_beneficiary_type:
            raise ValueError("beneficiary type must match request_type")
        expected_total = (
            self.details.invoice_gross_amount
            if isinstance(self.details, VendorPaymentDetails)
            else self.details.claimed_amount
        )
        if self.total_amount != expected_total:
            raise ValueError("total_amount must match the type-specific payment amount")
        if (self.request_number is None) is not (self.submitted_version is None):
            raise ValueError("request_number and submitted_version must be set together")
        if self.lifecycle_state not in {LifecycleState.DRAFT, LifecycleState.CANCELLED} and (
            self.request_number is None or self.submitted_version is None
        ):
            raise ValueError("submitted requests require a request number and submitted version")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self
