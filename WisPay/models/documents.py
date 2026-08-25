from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ._base import AwareDateTime, NonEmptyStr, Sha256Digest, WisPayBaseModel
from .enums import (
    AccessClassification,
    DocumentCategory,
    EvidenceValidationResult,
    ExceptionSeverity,
    ExceptionStatus,
    MalwareScanResult,
    MatchDecisionStatus,
    RequestType,
)
from .money import Money
from .references import AccountingDimension, UserSnapshot


class SupportingDocument(WisPayBaseModel):
    document_id: UUID
    request_id: UUID
    category: DocumentCategory
    filename: NonEmptyStr
    storage_path: NonEmptyStr
    size_bytes: int = Field(gt=0)
    mime_type: NonEmptyStr
    checksum: Sha256Digest
    version: int = Field(ge=1)
    uploader: UserSnapshot
    uploaded_at: AwareDateTime
    malware_scan_result: MalwareScanResult
    retention_category: NonEmptyStr
    access_classification: AccessClassification
    supersedes_document_id: UUID | None = None


class ExtractedInvoiceHeader(WisPayBaseModel):
    invoice_number: NonEmptyStr
    invoice_date: date
    vendor_name: NonEmptyStr
    gross_amount: Money
    purchase_order_reference: NonEmptyStr | None = None


class ExtractedInvoiceLine(WisPayBaseModel):
    line_id: NonEmptyStr
    description: NonEmptyStr
    quantity: Decimal = Field(gt=Decimal("0"), allow_inf_nan=False)
    unit_price: Money
    line_total: Money
    accounting_dimension: AccountingDimension | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("quantities must not use floating-point values")
        return value


class PurchaseOrderLineReferenceSnapshot(WisPayBaseModel):
    line_reference: NonEmptyStr
    description: NonEmptyStr
    quantity: Decimal = Field(gt=Decimal("0"), allow_inf_nan=False)
    line_total: Money
    accounting_dimension: AccountingDimension | None = None
    captured_at: AwareDateTime

    @field_validator("quantity", mode="before")
    @classmethod
    def reject_float_quantity(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("quantities must not use floating-point values")
        return value


class MatchConfidence(WisPayBaseModel):
    score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False)

    @field_validator("score", mode="before")
    @classmethod
    def reject_float_score(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("match confidence must not use floating-point values")
        return value


class MatchProposal(WisPayBaseModel):
    proposal_id: UUID
    invoice_line_id: NonEmptyStr
    purchase_order_line: PurchaseOrderLineReferenceSnapshot
    confidence: MatchConfidence
    reason: NonEmptyStr


class MatchDecision(WisPayBaseModel):
    proposal_id: UUID
    decision: MatchDecisionStatus
    decided_by: UserSnapshot
    decided_at: AwareDateTime
    reason: NonEmptyStr | None = None


class HumanReviewResult(WisPayBaseModel):
    decision: MatchDecisionStatus
    reviewer: UserSnapshot
    reviewed_at: AwareDateTime
    reason: NonEmptyStr


class EvidenceValidation(WisPayBaseModel):
    validation_id: UUID
    request_id: UUID
    request_type: RequestType
    result: EvidenceValidationResult
    reviewer: UserSnapshot
    reviewed_at: AwareDateTime
    matching_proposals: tuple[MatchProposal, ...] = ()
    match_decisions: tuple[MatchDecision, ...] = ()
    human_review: HumanReviewResult | None = None
    checklist_answers: tuple[tuple[NonEmptyStr, NonEmptyStr], ...] = ()
    exception_ids: tuple[UUID, ...] = ()
    reason: NonEmptyStr | None = None


class Exception(WisPayBaseModel):
    exception_id: UUID
    request_id: UUID
    exception_type: NonEmptyStr
    severity: ExceptionSeverity
    source_control: NonEmptyStr
    reason: NonEmptyStr
    status: ExceptionStatus = ExceptionStatus.OPEN
    resolution_reason: NonEmptyStr | None = None
    resolved_by: UserSnapshot | None = None
    resolved_at: AwareDateTime | None = None

    @model_validator(mode="after")
    def require_resolution_evidence(self) -> Self:
        resolved = self.status is not ExceptionStatus.OPEN
        evidence = (self.resolution_reason, self.resolved_by, self.resolved_at)
        if resolved and not all(value is not None for value in evidence):
            raise ValueError("resolved exceptions require reason, actor, and timestamp")
        if not resolved and any(value is not None for value in evidence):
            raise ValueError("open exceptions must not contain resolution evidence")
        return self
