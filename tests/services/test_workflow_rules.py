"""Tests for the versioned workflow-rule configuration and matcher."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from WisPay.models import Money, RequestType, RouteGenerationInput
from WisPay.models.enums import BudgetResult, RoleName
from WisPay.services.workflow_rules import (
    SEED_RULE_VERSION,
    THRESHOLDS_V1,
    WorkflowRule,
    matching_rules,
    seed_rules_v1,
)

_NOW = datetime(2026, 8, 26, tzinfo=UTC)


def _rule(**overrides: object) -> WorkflowRule:
    from WisPay.models.references import UserSnapshot

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
        "approver_user": UserSnapshot(
            external_identity_id="lm",
            display_name="LM",
            email="lm@wispay.example",
            captured_at=_NOW,
        ),
        "due_days": None,
    }
    defaults.update(overrides)
    return WorkflowRule(**defaults)  # type: ignore[arg-type]


def _inputs(**overrides: object) -> RouteGenerationInput:
    values: dict[str, object] = {
        "request_type": RequestType.VENDOR,
        "amount": Money(amount=Decimal("5000000"), currency_code="VND", decimal_scale=0),
        "budget_result": BudgetResult.WITHIN_BUDGET,
        "legal_entity_code": "LE-01",
        "department_code": "CC-01",
        "project_code": None,
        "risk_flags": (),
    }
    values.update(overrides)
    return RouteGenerationInput(**values)  # type: ignore[arg-type]


def test_seed_rules_v1_shape() -> None:
    rules = seed_rules_v1()
    assert all(rule.version == SEED_RULE_VERSION for rule in rules)
    line_manager = rules[0]
    assert line_manager.approver_role is RoleName.LINE_MANAGER
    assert line_manager.step_sequence == 1
    assert line_manager.min_amount is None
    executive = [rule for rule in rules if rule.step_sequence == 2]
    assert len(executive) == len(THRESHOLDS_V1)
    assert {rule.currency_code for rule in executive} == set(THRESHOLDS_V1)
    assert all(rule.approver_role is RoleName.EXECUTIVE_APPROVER for rule in executive)


def test_small_request_matches_only_line_manager() -> None:
    matched = matching_rules(seed_rules_v1(), _inputs())
    assert [rule.step_sequence for rule in matched] == [1]


def test_threshold_request_adds_executive_step() -> None:
    threshold = THRESHOLDS_V1["VND"]
    matched = matching_rules(
        seed_rules_v1(),
        _inputs(amount=Money(amount=threshold, currency_code="VND", decimal_scale=0)),
    )
    assert [rule.step_sequence for rule in matched] == [1, 2]
    below = matching_rules(
        seed_rules_v1(),
        _inputs(amount=Money(amount=threshold - Decimal(1), currency_code="VND", decimal_scale=0)),
    )
    assert [rule.step_sequence for rule in below] == [1]


def test_min_amount_rule_never_applies_across_currencies() -> None:
    vnd_only = _rule(min_amount=Decimal("1"), currency_code="VND")
    matched = matching_rules(
        [vnd_only],
        _inputs(amount=Money(amount=Decimal("1000000"), currency_code="USD", decimal_scale=2)),
    )
    assert matched == ()


def test_filters_narrow_matching() -> None:
    scoped = _rule(legal_entity_code="LE-02")
    assert matching_rules([scoped], _inputs()) == ()
    assert matching_rules([scoped], _inputs(legal_entity_code="LE-02")) == (scoped,)
    dept = _rule(department_code="CC-99")
    assert matching_rules([dept], _inputs()) == ()
    project = _rule(project_code="P-1")
    assert matching_rules([project], _inputs(project_code=None)) == ()
    risk = _rule(risk_flag="duplicate-risk")
    assert matching_rules([risk], _inputs()) == ()
    assert matching_rules([risk], _inputs(risk_flags=("duplicate-risk",))) == (risk,)


def test_ordering_follows_priority_then_sequence() -> None:
    late = _rule(priority=90, step_sequence=3)
    early = _rule(priority=5, step_sequence=2)
    matched = matching_rules([late, early], _inputs())
    assert matched == (early, late)


def test_min_amount_without_currency_is_unsatifiable() -> None:
    broken = _rule(min_amount=Decimal(1))
    assert matching_rules([broken], _inputs()) == ()


def test_employee_rule_ignores_vendor_only_rows() -> None:
    vendor_only = _rule(request_type=RequestType.VENDOR)
    matched = matching_rules([vendor_only], _inputs(request_type=RequestType.EMPLOYEE))
    assert matched == ()
    assert matching_rules([vendor_only], _inputs()) == (vendor_only,)
