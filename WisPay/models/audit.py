from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from ._base import AwareDateTime, NonEmptyStr, Sha256Digest, WisPayBaseModel
from .enums import AuditAction, LegalHoldState
from .references import UserSnapshot


class RetentionPolicy(WisPayBaseModel):
    retention_policy_id: UUID
    category: NonEmptyStr
    period_days: int | None = Field(default=None, gt=0)
    disposition_rule: NonEmptyStr
    legal_hold_state: LegalHoldState = LegalHoldState.NONE
    approval_authority: NonEmptyStr
    version: NonEmptyStr
    effective_from: AwareDateTime
    effective_to: AwareDateTime | None = None

    @model_validator(mode="after")
    def validate_effective_dates(self) -> Self:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


_REASON_REQUIRED_ACTIONS = frozenset(
    {
        AuditAction.REJECTED,
        AuditAction.RETURNED,
        AuditAction.CANCELLED,
        AuditAction.EXCEPTION_RECORDED,
        AuditAction.AUTHORIZATION_DENIED,
        AuditAction.CONFIGURATION_CHANGED,
    }
)


class AuditValueSnapshot(WisPayBaseModel):
    """Canonical JSON captured before hashing and append-only persistence."""

    canonical_json: NonEmptyStr


class AuditEvent(WisPayBaseModel):
    audit_event_id: UUID
    entity_type: NonEmptyStr
    entity_id: NonEmptyStr
    actor: UserSnapshot
    action: AuditAction
    occurred_at: AwareDateTime
    old_value: AuditValueSnapshot | None = None
    new_value: AuditValueSnapshot | None = None
    reason: NonEmptyStr | None = None
    correlation_id: NonEmptyStr
    impersonation_context: NonEmptyStr | None = None
    delegation_id: UUID | None = None
    previous_hash: Sha256Digest | None = None
    event_hash: Sha256Digest
    retention_policy_id: UUID
    legal_hold: bool = False

    @model_validator(mode="after")
    def require_reason_for_consequential_actions(self) -> Self:
        if self.action in _REASON_REQUIRED_ACTIONS and self.reason is None:
            raise ValueError(f"{self.action.value} audit events require a reason")
        return self
