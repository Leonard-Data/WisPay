from __future__ import annotations

from datetime import date
from typing import Self
from uuid import UUID

from pydantic import model_validator

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import PaymentReconciliationState
from .money import Money
from .references import UserSnapshot


class PaymentRecord(WisPayBaseModel):
    payment_record_id: UUID
    request_id: UUID
    payment_date: date
    amount: Money
    method: NonEmptyStr
    external_reference: NonEmptyStr
    accounting_reference: NonEmptyStr | None = None
    proof_document_id: UUID
    operator: UserSnapshot
    reconciliation_state: PaymentReconciliationState = PaymentReconciliationState.PENDING
    recorded_at: AwareDateTime
    reconciled_at: AwareDateTime | None = None

    @model_validator(mode="after")
    def validate_reconciliation_evidence(self) -> Self:
        reconciled = self.reconciliation_state is not PaymentReconciliationState.PENDING
        if reconciled and self.reconciled_at is None:
            raise ValueError("reconciled payment records require reconciled_at")
        if not reconciled and self.reconciled_at is not None:
            raise ValueError("pending payment records must not have reconciled_at")
        return self
