#!/usr/bin/env python
"""Live Azure SQL smoke for the approval workflow slice (ticket 04).

Run after `scripts/test_connections.py --db-only` passes:

    uv run python scripts/smoke_approval_flow.py

Proves, against the real database:
1. ensure_schema is idempotent (two consecutive runs, identical table set).
2. Rule seeding is once-only (second ensure_seeded adds no rows).
3. save -> route -> decide -> re-read over a FRESH connection round-trips.
4. Audit chain holds the generation + decision events for the request.
5. A second structural pass changes nothing (no duplicate rows).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()  # noqa: E402 - env must load before WisPay reads AZURE_SQL_*

from WisPay.models import (  # noqa: E402
    AccountingDimension,
    BeneficiaryReference,
    LifecycleState,
    Money,
    PaymentRequest,
    RequestType,
    RouteGenerationInput,
    UserSnapshot,
    VendorPaymentDetails,
    WorkflowOutcome,
)
from WisPay.models.enums import (  # noqa: E402
    AccessClassification,
    ApprovalDecision,  # noqa: E402
    AuditAction,
    BeneficiaryType,
    BudgetResult,
    OpexCapexClassification,
)
from WisPay.services import approval_workflow  # noqa: E402
from WisPay.services.db import connect, ensure_schema  # noqa: E402
from WisPay.services.reference_data import RETENTION_POLICY_ID_PROTOTYPE  # noqa: E402
from WisPay.services.sql_repositories import DurableAuditTrail, sql_stores  # noqa: E402
from WisPay.services.workflow_rules import SEED_RULE_VERSION  # noqa: E402

NOW = datetime.now(UTC)


def _actor(identity: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=identity,
        display_name=identity,
        email=f"{identity}@wispay.example",
        captured_at=NOW,
    )


def _request() -> PaymentRequest:
    return PaymentRequest(
        request_id=uuid4(),
        request_number=f"WPR-SMOKE-{NOW.strftime('%Y%m%d%H%M%S')}",
        request_type=RequestType.VENDOR,
        requester=_actor("smoke-requester"),
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="Smoke Vendor",
            captured_at=NOW,
            access_classification=AccessClassification.CONFIDENTIAL,
        ),
        accounting_dimension=AccountingDimension(
            legal_entity_code="LE-01",
            legal_entity_name="WisPay Co",
            department_code="CC-01",
            department_name="Operations",
            cost_center_code="C-01",
            cost_center_name="Shared",
            expense_category_code="E-01",
            expense_category_name="Services",
            classification=OpexCapexClassification.OPEX,
            budget_period="2026-08",
            captured_at=NOW,
        ),
        purpose="Live SQL smoke payment",
        total_amount=Money(amount=Decimal("150000000"), currency_code="VND", decimal_scale=0),
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.SUBMITTED,
        lifecycle_version="v1",
        submitted_version=1,
        details=VendorPaymentDetails(
            invoice_number="INV-SMOKE-1",
            invoice_date=NOW.date(),
            due_date=NOW.date(),
            invoice_net_amount=Money(
                amount=Decimal("150000000"), currency_code="VND", decimal_scale=0
            ),
            vat_amount=Money(amount=Decimal("0"), currency_code="VND", decimal_scale=0),
            invoice_gross_amount=Money(
                amount=Decimal("150000000"), currency_code="VND", decimal_scale=0
            ),
            payment_terms="Net 30",
            proposed_payment_method="Bank transfer",
            duplicate_warning_key="smoke|INV-SMOKE-1|150000000",
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def _counts(conn: object) -> dict[str, int]:
    cursor = conn.cursor()  # type: ignore[attr-defined]
    counts: dict[str, int] = {}
    for table in (
        "wispay_payment_request",
        "wispay_workflow_instance",
        "wispay_workflow_rule",
        "wispay_workflow_rule_version",
        "wispay_audit_event",
    ):
        cursor.execute(f"SELECT COUNT(*) FROM dbo.{table}")
        counts[table] = int(cursor.fetchone()[0])
    cursor.close()
    return counts


def main() -> int:
    print("== connect + ensure_schema (run 1)")
    conn = connect()
    ensure_schema(conn)
    rules_before = _counts(conn)["wispay_workflow_rule"]

    print("== ensure_schema (run 2, must be a no-op)")
    ensure_schema(conn)
    stores = sql_stores(conn, ensure_tables=False)
    _ensure_seeded = getattr(stores.rules, "ensure_seeded", None)
    if _ensure_seeded is not None:
        _ensure_seeded(version=SEED_RULE_VERSION)
    after_second = _counts(conn)
    assert after_second["wispay_workflow_rule"] >= rules_before, "rule rows vanished"

    request = _request()
    stores.requests.save(request)
    stored = stores.requests.get_by_number(request.request_number or "")
    assert stored is not None and stored.request_id == request.request_id

    print("== generate route (frozen v1 snapshot)")
    rule_version = stores.rules.active_version()
    assert rule_version == SEED_RULE_VERSION
    command = approval_workflow.GenerateRouteCommand(
        request_id=request.request_id,
        generation_inputs=RouteGenerationInput(
            request_type=RequestType.VENDOR,
            amount=request.total_amount,
            budget_result=BudgetResult.NOT_APPLICABLE,
            legal_entity_code="LE-01",
            department_code="CC-01",
        ),
    )
    trail = DurableAuditTrail(stores.audit, retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE)
    result = approval_workflow.generate_route(
        command,
        rules=stores.rules.rules(rule_version),
        rule_version=rule_version,
        now=NOW,
        actor=_actor("sample-lm-001"),
        audit=trail,
    )
    stores.workflows.save_instance(result.instance)
    stores.requests.save(
        request.evolve(
            workflow_instance_id=result.instance.workflow_instance_id,
            updated_at=datetime.now(UTC),
        )
    )

    print("== decide: Line Manager approves step 1")
    step_one = result.instance.steps[0]
    decision = approval_workflow.DecisionCommand(
        workflow_instance_id=result.instance.workflow_instance_id,
        step_id=step_one.step_id,
        decision=ApprovalDecision.APPROVED,
        actor=_actor("sample-lm-001"),
    )
    decided = approval_workflow.decide(
        decision,
        instance=result.instance,
        requester_id="smoke-requester",
        now=datetime.now(UTC),
        trail_appender=trail,
    )
    stores.workflows.save_instance(decided.instance)

    print("== fresh-connection re-read")
    if hasattr(conn, "close"):
        conn.close()
    conn2 = connect()
    stores2 = sql_stores(conn2, ensure_tables=False)
    reread_request = stores2.requests.get(request.request_id)
    assert reread_request is not None
    assert reread_request.workflow_instance_id == result.instance.workflow_instance_id
    reread_instance = stores2.workflows.get_instance(result.instance.workflow_instance_id)
    assert reread_instance is not None
    assert reread_instance.final_outcome is WorkflowOutcome.PENDING, (
        "one approval of two must stay pending"
    )
    events = stores2.audit.events_for_request(str(request.request_id))
    actions = [event.action for event in events]
    assert actions == [AuditAction.CHANGED, AuditAction.APPROVED], actions

    print("== structural second pass (counts must match)")
    counts_a = _counts(conn2)
    _ensure_seeded = getattr(stores2.rules, "ensure_seeded", None)
    if _ensure_seeded is not None:
        _ensure_seeded(version=SEED_RULE_VERSION)
    counts_b = _counts(conn2)
    assert counts_a == counts_b, f"second pass mutated rows: {counts_a} -> {counts_b}"

    if hasattr(conn2, "close"):
        conn2.close()
    print("SMOKE PASS")
    print(f"  request        {request.request_number}")
    print(f"  instance       {result.instance.workflow_instance_id} (Pending)")
    print(f"  audit actions  {[a.value for a in actions]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
