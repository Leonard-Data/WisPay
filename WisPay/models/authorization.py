from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import DelegationStatus, RoleName
from .references import UserSnapshot


class RoleAssignment(WisPayBaseModel):
    assignment_id: UUID
    user: UserSnapshot
    role: RoleName
    organization_scope: NonEmptyStr
    source: NonEmptyStr
    starts_at: AwareDateTime
    ends_at: AwareDateTime | None = None
    version: NonEmptyStr

    @model_validator(mode="after")
    def validate_effective_dates(self) -> Self:
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class DelegationScope(WisPayBaseModel):
    scope_type: NonEmptyStr
    scope_value: NonEmptyStr


class Delegation(WisPayBaseModel):
    delegation_id: UUID
    delegator: UserSnapshot
    delegate: UserSnapshot
    scopes: tuple[DelegationScope, ...]
    allowed_actions: tuple[NonEmptyStr, ...]
    starts_at: AwareDateTime
    ends_at: AwareDateTime
    reason: NonEmptyStr
    created_by: UserSnapshot
    approved_by: UserSnapshot | None = None
    status: DelegationStatus
    created_at: AwareDateTime

    @model_validator(mode="after")
    def validate_delegation(self) -> Self:
        if self.delegator.external_identity_id == self.delegate.external_identity_id:
            raise ValueError("delegator and delegate must be different users")
        if self.ends_at <= self.starts_at:
            raise ValueError("delegation end must be after its start")
        if not self.scopes or not self.allowed_actions:
            raise ValueError("delegations require scope and allowed actions")
        return self


class PermissionRule(WisPayBaseModel):
    role: RoleName
    action_family: NonEmptyStr
    organization_scope: NonEmptyStr | None = None
    allows: bool


class PermissionRuleVersion(WisPayBaseModel):
    version: NonEmptyStr
    effective_from: AwareDateTime
    effective_to: AwareDateTime | None = None
    rules: tuple[PermissionRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_effective_dates(self) -> Self:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self
