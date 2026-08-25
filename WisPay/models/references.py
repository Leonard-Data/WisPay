from __future__ import annotations

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import (
    AccessClassification,
    BeneficiaryType,
    OpexCapexClassification,
)


class BankReferenceSnapshot(WisPayBaseModel):
    reference_id: NonEmptyStr
    bank_name: NonEmptyStr
    masked_account: NonEmptyStr
    captured_at: AwareDateTime
    independently_verified: bool = False


class UserSnapshot(WisPayBaseModel):
    external_identity_id: NonEmptyStr
    display_name: NonEmptyStr
    email: NonEmptyStr
    department: NonEmptyStr | None = None
    organization_scopes: tuple[NonEmptyStr, ...] = ()
    captured_at: AwareDateTime


class UserReference(UserSnapshot):
    is_active: bool
    last_synced_at: AwareDateTime


class BeneficiaryReference(WisPayBaseModel):
    beneficiary_type: BeneficiaryType
    external_master_data_id: NonEmptyStr | None = None
    display_name: NonEmptyStr
    tax_or_employee_reference: NonEmptyStr | None = None
    bank_reference: BankReferenceSnapshot | None = None
    access_classification: AccessClassification = AccessClassification.RESTRICTED
    captured_at: AwareDateTime


class AccountingDimension(WisPayBaseModel):
    legal_entity_code: NonEmptyStr
    legal_entity_name: NonEmptyStr
    department_code: NonEmptyStr
    department_name: NonEmptyStr
    cost_center_code: NonEmptyStr
    cost_center_name: NonEmptyStr
    project_code: NonEmptyStr | None = None
    project_name: NonEmptyStr | None = None
    expense_category_code: NonEmptyStr
    expense_category_name: NonEmptyStr
    classification: OpexCapexClassification
    budget_period: NonEmptyStr
    captured_at: AwareDateTime
