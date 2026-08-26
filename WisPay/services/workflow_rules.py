"""Versioned approval-route rules and sample configuration.

Rule rows are application configuration (service layer, per CONVENTIONS.md),
not canonical domain records. ``matching_rules`` is purely row-driven so a
future admin-managed rule table needs no code change; the shipped ``v1`` seed
set is generated from ``THRESHOLDS_V1`` and is visibly labeled sample
configuration until policy sign-off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from WisPay.models.enums import RequestType, RoleName
from WisPay.models.references import UserSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from WisPay.models import RouteGenerationInput

SEED_RULE_VERSION = "v1"

# Sample actors — placeholder identities until authentication lands (Entra ID
# work owns real identity). Emails use the reserved example TLD on purpose.
_ACTOR_STAMP = datetime(2026, 1, 1, tzinfo=UTC)

SAMPLE_APPROVER_LINE_MANAGER = UserSnapshot(
    external_identity_id="sample-lm-001",
    display_name="Minh Nguyen",
    email="minh.nguyen@wispay.example",
    department="Operations",
    captured_at=_ACTOR_STAMP,
)
SAMPLE_APPROVER_EXECUTIVE = UserSnapshot(
    external_identity_id="sample-cfo-001",
    display_name="Lan Pham",
    email="lan.pham@wispay.example",
    department="Executive",
    captured_at=_ACTOR_STAMP,
)

#: Amount-at-or-above thresholds (request currency) that add the executive
#: approval step under the v1 seed set. Sample values — not policy.
THRESHOLDS_V1: dict[str, Decimal] = {
    "VND": Decimal("100000000"),
    "USD": Decimal("10000"),
    "EUR": Decimal("10000"),
}

_THRESHOLD_PRIORITY_BASE = 20


@dataclass(frozen=True, slots=True)
class WorkflowRule:
    """One versioned approval-route row.

    ``None`` filter fields mean "any". A monetary filter is only evaluable
    together with its ``currency_code``; a ``min_amount`` without a currency is
    treated as unsatisfiable rather than guessed.
    """

    version: str
    priority: int
    request_type: RequestType | None
    min_amount: Decimal | None
    currency_code: str | None
    legal_entity_code: str | None
    department_code: str | None
    project_code: str | None
    risk_flag: str | None
    step_sequence: int
    parallel_group: str | None
    approver_role: RoleName
    approver_user: UserSnapshot
    due_days: int | None


def seed_rules_v1() -> tuple[WorkflowRule, ...]:
    """Return the v1 sample rule set: line manager always, executive at/above
    the per-currency threshold."""

    def _base(**overrides: object) -> WorkflowRule:
        defaults: dict[str, object] = {
            "version": SEED_RULE_VERSION,
            "priority": 10,
            "request_type": None,
            "min_amount": None,
            "currency_code": None,
            "legal_entity_code": None,
            "department_code": None,
            "project_code": None,
            "risk_flag": None,
            "step_sequence": 1,
            "parallel_group": None,
            "approver_role": RoleName.LINE_MANAGER,
            "approver_user": SAMPLE_APPROVER_LINE_MANAGER,
            "due_days": 3,
        }
        defaults.update(overrides)
        return WorkflowRule(**defaults)  # type: ignore[arg-type] # typed dict above

    executive_rows = [
        _base(
            priority=_THRESHOLD_PRIORITY_BASE + offset,
            min_amount=threshold,
            currency_code=currency,
            step_sequence=2,
            approver_role=RoleName.EXECUTIVE_APPROVER,
            approver_user=SAMPLE_APPROVER_EXECUTIVE,
            due_days=5,
        )
        for offset, (currency, threshold) in enumerate(THRESHOLDS_V1.items())
    ]
    return (_base(), *executive_rows)


def _rule_applies(rule: WorkflowRule, inputs: RouteGenerationInput) -> bool:
    if rule.request_type is not None and rule.request_type is not inputs.request_type:
        return False
    if rule.min_amount is not None:
        if rule.currency_code is None or rule.currency_code != inputs.amount.currency_code:
            return False
        if inputs.amount.amount < rule.min_amount:
            return False
    elif rule.currency_code is not None and rule.currency_code != inputs.amount.currency_code:
        return False
    if rule.legal_entity_code is not None and rule.legal_entity_code != inputs.legal_entity_code:
        return False
    if rule.department_code is not None and rule.department_code != inputs.department_code:
        return False
    if rule.project_code is not None and rule.project_code != inputs.project_code:
        return False
    return not (rule.risk_flag is not None and rule.risk_flag not in inputs.risk_flags)


def matching_rules(
    rules: Sequence[WorkflowRule],
    inputs: RouteGenerationInput,
) -> tuple[WorkflowRule, ...]:
    """Return applicable rules ordered by ``(priority, step_sequence)``."""
    applicable = [rule for rule in rules if _rule_applies(rule, inputs)]
    applicable.sort(key=lambda rule: (rule.priority, rule.step_sequence))
    return tuple(applicable)
