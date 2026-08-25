from __future__ import annotations

from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import (
    ApprovalDecision,
    BudgetResult,
    RequestType,
    ReviewResult,
    RoleName,
    WorkflowOutcome,
)
from .money import Money
from .references import UserSnapshot


class ChecklistAnswer(WisPayBaseModel):
    question_id: NonEmptyStr
    answer: bool | NonEmptyStr | Decimal | None
    reason: NonEmptyStr | None = None


class BudgetCheck(WisPayBaseModel):
    check_id: UUID
    request_id: UUID
    result: BudgetResult
    reviewer: UserSnapshot
    amount_checked: Money
    budget_source: NonEmptyStr
    budget_owner: UserSnapshot | None = None
    evidence_document_id: UUID | None = None
    reason: NonEmptyStr | None = None
    reviewed_at: AwareDateTime

    @model_validator(mode="after")
    def require_over_budget_reason(self) -> Self:
        if self.result is BudgetResult.OVER_BUDGET_EXCEPTION_REQUIRED and self.reason is None:
            raise ValueError("over-budget checks require a reason")
        return self


class ComplianceReview(WisPayBaseModel):
    review_id: UUID
    request_id: UUID
    checklist_version: NonEmptyStr
    reviewer: UserSnapshot
    answers: tuple[ChecklistAnswer, ...]
    result: ReviewResult
    reasons: tuple[NonEmptyStr, ...] = ()
    exception_ids: tuple[UUID, ...] = ()
    reviewed_at: AwareDateTime

    @model_validator(mode="after")
    def require_non_pass_reason(self) -> Self:
        if self.result is not ReviewResult.PASSED and not self.reasons:
            raise ValueError("non-passing compliance reviews require a reason")
        return self


class RouteGenerationInput(WisPayBaseModel):
    request_type: RequestType
    amount: Money
    budget_result: BudgetResult
    legal_entity_code: NonEmptyStr
    department_code: NonEmptyStr
    project_code: NonEmptyStr | None = None
    risk_flags: tuple[NonEmptyStr, ...] = ()


class ApprovalStep(WisPayBaseModel):
    step_id: UUID
    sequence: int = Field(ge=1)
    parallel_group: NonEmptyStr | None = None
    approver: UserSnapshot
    role: RoleName
    delegated_from: UserSnapshot | None = None
    due_at: AwareDateTime | None = None
    decision: ApprovalDecision = ApprovalDecision.PENDING
    reason: NonEmptyStr | None = None
    comments: tuple[NonEmptyStr, ...] = ()
    decided_at: AwareDateTime | None = None

    @model_validator(mode="after")
    def validate_decision_evidence(self) -> Self:
        if self.decision is ApprovalDecision.PENDING and self.decided_at is not None:
            raise ValueError("pending approval steps must not have a decision timestamp")
        if self.decision is not ApprovalDecision.PENDING and self.decided_at is None:
            raise ValueError("completed approval steps require a decision timestamp")
        if self.decision in {ApprovalDecision.RETURNED, ApprovalDecision.REJECTED} and (
            self.reason is None
        ):
            raise ValueError("returned and rejected approval steps require a reason")
        return self


class WorkflowInstance(WisPayBaseModel):
    workflow_instance_id: UUID
    request_id: UUID
    workflow_rule_version: NonEmptyStr
    generation_inputs: RouteGenerationInput
    steps: tuple[ApprovalStep, ...] = Field(min_length=1)
    current_step_sequence: int | None = Field(default=None, ge=1)
    final_outcome: WorkflowOutcome = WorkflowOutcome.PENDING
    generated_at: AwareDateTime
