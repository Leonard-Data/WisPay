# 02 — Approval workflow services (rules, route generation, decisions)

Status: claimed
Feature: `.scratch/approval-workflow/spec.md` (read first — contracts pinned there)

## Target

New files only:
- `WisPay/services/workflow_rules.py`
- `WisPay/services/approval_workflow.py`
- `tests/services/test_workflow_rules.py`
- `tests/services/test_approval_workflow.py`

Do NOT touch: models, other services, states, pages, routers, assets.

## Change

Implement exactly the contracts in spec §"Workflow rules + services": `WorkflowRule`,
sample approver/requester snapshots (labeled sample configuration, consistent with
`reference_data.py::REQUESTER_PROTOTYPE` style), `THRESHOLDS_V1`, `seed_rules_v1()`,
`matching_rules()`; `GenerateRouteCommand`, `DecisionCommand`, typed error hierarchy,
`generate_route()`, `decide()` with `RouteResult` / `DecisionResult`.

Guard order in `decide` exactly as spec: route open → step known → pending & actionable
(earliest pending sequence or same parallel group) → not self-approval → actor is step
approver → reason required on Reject/Return. Completion rule: all steps decided Approved ⇒
`final_outcome=Approved`, `route_completed=True`; any Rejected ⇒ outcome Rejected;
Returned leaves future pending steps untouched (frozen snapshot). One `AuditEvent` per
decision (action `Approved/Rejected/Returned`, `entity_type="approval_step"`,
`correlation_id=str(request_id)`) appended via injected `trail_appender`. Route generation
requires ≥1 matching rule else `NoRouteError`; stamps `workflow_rule_version`, freezes
`generation_inputs`, builds steps with `uuid4()` ids and `due_at = now + due_days`.

Pure domain per ADR-0005: no Reflex, no pyodbc, no env access, no I/O beyond the injected
appender. Frozen model rebuilds only — never mutate. Money comparisons only within equal
currency codes; threshold match uses the request currency's entry (missing entry ⇒ rule
does not apply). Timezone-aware datetimes everywhere. `Money` equality/comparison helpers
from `WisPay.models.money` as needed.

## Tests (no skips)

Cover: seed rules shape; matcher filtering by type/amount-threshold/entity/project/risk and
priority ordering; generate_route snapshot fidelity (version, inputs, ordered steps, due
dates); happy approve-all path to `route_completed=True`; reject closes route; return keeps
future steps Pending; every guard raises its typed error (self-approval, wrong approver,
non-current step, missing reason, closed route, unknown step); exactly one audit event per
decision with correct action/entity/correlation; hash-chained events verify using
`audit_trail.chain_hash` over `canonical_payload`.

## Acceptance

- `uv run pytest tests/services -q` green alongside ticket 01's files.
- ruff/mypy --strict clean; line length 100.
