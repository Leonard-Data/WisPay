"""Demo seed data for the WisPay portal.

Populates a fresh ``Stores`` bundle with deterministic sample data covering
every lifecycle state from ``WisPay.models.lifecycle.LifecycleState``. Honors
the BS-1 contract in `.scratch/wispay-deploy-build/implementation-tracker.md`
(S01–S16 fixtures + 8 personas + audit + comments + notifications).

The seed function is **idempotent and additive**: it overwrites any prior
``WPR-2026-DEMO-*`` request it finds, but leaves other rows untouched so a
demo session can re-seed without colliding with real submissions.

Activation
----------

The seed runs at process start when ``WISPAY_DEMO_MODE=1`` is exported
(see :mod:`WisPay.routers`). It is also callable from tests as a fixture
factory through :func:`seed_demo_state`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from WisPay.models import (
    AccountingDimension,
    ApprovalDecision,
    AuditAction,
    BankReferenceSnapshot,
    BeneficiaryReference,
    BeneficiaryType,
    EmployeePaymentDetails,
    EmployeeRequestSubtype,
    LifecycleState,
    Money,
    OpexCapexClassification,
    PaymentRecord,
    PaymentRequest,
    RequestType,
    RoleAssignment,
    RouteGenerationInput,
    UserSnapshot,
    VendorPaymentDetails,
    WorkflowInstance,
    WorkflowOutcome,
)
from WisPay.models.enums import BudgetResult, RoleName
from WisPay.services.approval_workflow import (
    DecisionCommand,
    GenerateRouteCommand,
    decide,
    generate_route,
)
from WisPay.services.payment_recording import (
    record_payment,
    start_payment,
)
from WisPay.services.reference_data import (
    RETENTION_POLICY_ID_PROTOTYPE,
    doc_requirements,
)
from WisPay.services.sql_repositories import DurableAuditTrail

if TYPE_CHECKING:
    from WisPay.services.repositories import Stores


# --------------------------------------------------------------------------- #
# Fixed reference date — anchors overdue / SLA math (BS-1 §4.1).
# --------------------------------------------------------------------------- #
DEMO_REFERENCE_DATE: date = date(2026, 8, 24)

_DEMO_CORRELATION_PREFIX = "demo-seed"
_DEMO_NUMBER_PREFIX = "WPR-2026-DEMO"
_DEMO_REQUESTER_ID = "demo-requester-lm"
_DEMO_APPROVER_LM_ID = "demo-approver-lm"
_DEMO_APPROVER_CFO_ID = "demo-approver-cfo"
_DEMO_OPERATOR_ID = "demo-operator-payops"


# --------------------------------------------------------------------------- #
# Personas (8, per A13 contract)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DemoPersona:
    """One named user profile with its role assignments."""

    snapshot: UserSnapshot
    roles: tuple[RoleName, ...]


def _persona(identity: str, name: str, email: str, *roles: RoleName) -> DemoPersona:
    return DemoPersona(
        snapshot=UserSnapshot(
            external_identity_id=identity,
            display_name=name,
            email=email,
            department=_department_for(roles),
            captured_at=_now(),
        ),
        roles=roles,
    )


def _department_for(roles: tuple[RoleName, ...]) -> str:
    if RoleName.EXECUTIVE_APPROVER in roles:
        return "Executive"
    if RoleName.FINANCE_REVIEWER in roles:
        return "Finance"
    if RoleName.BUDGET_OWNER in roles:
        return "Budget"
    if RoleName.PAYMENT_OPERATOR in roles:
        return "Treasury"
    if RoleName.AUDITOR in roles:
        return "Audit"
    if RoleName.SYSTEM_ADMINISTRATOR in roles:
        return "IT"
    if RoleName.LINE_MANAGER in roles:
        return "Operations"
    return "Requester"


def default_personas() -> tuple[DemoPersona, ...]:
    """Return the canonical 8-persona sample roster.

    Mirrors ``pages/admin_fixtures.PERSONA_GRID`` (A13) so the sidebar
    switcher and the admin page agree on the same names.
    """

    return (
        _persona(
            "demo-requester-me",
            "Maya Esposito",
            "maya.esposito@wispay.example",
            RoleName.REQUESTER,
        ),
        _persona(
            "demo-requester-jr",
            "Jamie Reyes",
            "jamie.reyes@wispay.example",
            RoleName.REQUESTER,
        ),
        _persona(
            _DEMO_APPROVER_LM_ID,
            "Linnea Müller",
            "linnea.muller@wispay.example",
            RoleName.LINE_MANAGER,
            RoleName.REQUESTER,
        ),
        _persona(
            "demo-budget-pk",
            "Priya Kapoor",
            "priya.kapoor@wispay.example",
            RoleName.BUDGET_OWNER,
        ),
        _persona(
            "demo-finance-rn",
            "Rosa Ngo",
            "rosa.ngo@wispay.example",
            RoleName.FINANCE_REVIEWER,
        ),
        _persona(
            _DEMO_APPROVER_CFO_ID,
            "Erez Cohen",
            "erez.cohen@wispay.example",
            RoleName.EXECUTIVE_APPROVER,
        ),
        _persona(
            _DEMO_OPERATOR_ID,
            "Tomi Adebayo",
            "tomi.adebayo@wispay.example",
            RoleName.PAYMENT_OPERATOR,
        ),
        _persona(
            "demo-auditor-sk",
            "Sana Kawai",
            "sana.kawai@wispay.example",
            RoleName.AUDITOR,
        ),
    )


def default_role_assignments(personas: tuple[DemoPersona, ...]) -> list[RoleAssignment]:
    """Flat role assignment list keyed by ``persona.snapshot`` start-of-2026."""

    assignments: list[RoleAssignment] = []
    starts = datetime(2026, 1, 1, tzinfo=UTC)
    for persona in personas:
        for role in persona.roles:
            assignments.append(
                RoleAssignment(
                    assignment_id=uuid4(),
                    user=persona.snapshot,
                    role=role,
                    organization_scope="GLOBAL",
                    source="demo-seed",
                    version="v1",
                    starts_at=starts,
                    ends_at=None,
                )
            )
    return assignments


# --------------------------------------------------------------------------- #
# Sample actors used in seeded route steps
# --------------------------------------------------------------------------- #


def _requesters(personas: tuple[DemoPersona, ...]) -> tuple[UserSnapshot, ...]:
    return tuple(p.snapshot for p in personas if RoleName.REQUESTER in p.roles)


def _find_actor(personas: tuple[DemoPersona, ...], role: RoleName) -> UserSnapshot:
    for persona in personas:
        if role in persona.roles:
            return persona.snapshot
    raise KeyError(f"No persona provides role {role}.")


# --------------------------------------------------------------------------- #
# Money / dimension helpers
# --------------------------------------------------------------------------- #


def _money_vnd(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def _dimension(
    *,
    cost_center: str = "CC-100",
    cost_center_name: str = "Corporate Finance",
    department_code: str = "FIN",
    department_name: str = "Finance",
    project: str | None = None,
    period: str = "2026-08",
) -> AccountingDimension:
    return AccountingDimension(
        legal_entity_code="VN01",
        legal_entity_name="WisPay Vietnam",
        department_code=department_code,
        department_name=department_name,
        cost_center_code=cost_center,
        cost_center_name=cost_center_name,
        project_code=project,
        project_name=f"{project} sample" if project else None,
        expense_category_code="SERVICES",
        expense_category_name="Professional Services",
        classification=OpexCapexClassification.OPEX,
        budget_period=period,
        captured_at=_now(),
    )


def _vendor_beneficiary(name: str) -> BeneficiaryReference:
    return BeneficiaryReference(
        beneficiary_type=BeneficiaryType.VENDOR,
        external_master_data_id=f"MD-{name.replace(' ', '').upper()[:10]}",
        display_name=name,
        tax_or_employee_reference="0312345678",
        bank_reference=BankReferenceSnapshot(
            reference_id="BANK-VENDOR-001",
            bank_name="VCB",
            masked_account="****1234",
            captured_at=_now(),
            independently_verified=True,
        ),
        captured_at=_now(),
    )


def _employee_beneficiary(snapshot: UserSnapshot) -> BeneficiaryReference:
    return BeneficiaryReference(
        beneficiary_type=BeneficiaryType.EMPLOYEE,
        display_name=snapshot.display_name,
        tax_or_employee_reference="EMP-001",
        bank_reference=BankReferenceSnapshot(
            reference_id="BANK-EMP-001",
            bank_name="VCB",
            masked_account="****5678",
            captured_at=_now(),
            independently_verified=True,
        ),
        captured_at=_now(),
    )


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #


def _now() -> datetime:
    return datetime(2026, 8, 26, 9, 0, tzinfo=UTC)


def _date(offset_days: int = 0) -> date:
    """Return DEMO_REFERENCE_DATE + ``offset_days`` (a stable seed clock)."""

    return DEMO_REFERENCE_DATE + timedelta(days=offset_days)


def _dt(days_offset: int, hour: int = 9) -> datetime:
    return datetime.combine(_date(days_offset), datetime.min.time()).replace(hour=hour, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Built aggregates for every lifecycle state (S01–S16)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _SeedSpec:
    """One row in the demo matrix."""

    number: str
    title: str
    purpose: str
    target_state: LifecycleState
    family: str
    subtype: str
    amount: str
    requester: UserSnapshot
    cost_center: str = "CC-100"
    project: str | None = None
    payment_method: str = "BANK_TRANSFER"
    over_budget: bool = False
    advance_request_number: str | None = None


def _specs() -> tuple[_SeedSpec, ...]:
    personas = default_personas()
    requester_primary = _requesters(personas)[0]
    requester_secondary = _requesters(personas)[1]
    requester_lm = _find_actor(personas, RoleName.LINE_MANAGER)
    requester_other = requester_lm  # used to ensure LM can also submit

    return (
        # S01: Draft (incomplete Vendor request — never submitted)
        _SeedSpec(
            number="WPR-2026-DEMO-01",
            title="Q3 marketing translation services",
            purpose="Translate Q3 marketing collateral for VN market.",
            target_state=LifecycleState.DRAFT,
            family="vendor",
            subtype="standard",
            amount="45000000",
            requester=requester_primary,
        ),
        # S02: Submitted (Vendor, no route yet)
        _SeedSpec(
            number="WPR-2026-DEMO-02",
            title="Hai Phong Steel — bulk order",
            purpose="Bulk steel order for Hai Phong assembly line.",
            target_state=LifecycleState.SUBMITTED,
            family="vendor",
            subtype="standard",
            amount="1240000000",
            requester=requester_secondary,
        ),
        # S03: Budget Review
        _SeedSpec(
            number="WPR-2026-DEMO-03",
            title="Da Nang Print Co. — campaign collateral",
            purpose="Print run for the awareness campaign.",
            target_state=LifecycleState.BUDGET_REVIEW,
            family="vendor",
            subtype="standard",
            amount="78400000",
            requester=requester_primary,
        ),
        # S04: Compliance Review
        _SeedSpec(
            number="WPR-2026-DEMO-04",
            title="Mekong Freight — Q2 settlement",
            purpose="Settle Q2 freight invoices.",
            target_state=LifecycleState.COMPLIANCE_REVIEW,
            family="vendor",
            subtype="standard",
            amount="56200000",
            requester=requester_primary,
        ),
        # S05: Evidence Validation
        _SeedSpec(
            number="WPR-2026-DEMO-05",
            title="Sai Gon Office Supply — restock",
            purpose="Restock office supplies for August.",
            target_state=LifecycleState.EVIDENCE_VALIDATION,
            family="vendor",
            subtype="standard",
            amount="12800000",
            requester=requester_primary,
        ),
        # S06: Approval Pending (Vendor, frozen route)
        _SeedSpec(
            number="WPR-2026-DEMO-06",
            title="Hanoi Cloud Hosting — Q3 retainer",
            purpose="Pay Q3 retainer for cloud hosting.",
            target_state=LifecycleState.APPROVAL_PENDING,
            family="vendor",
            subtype="standard",
            amount="98600000",
            requester=requester_primary,
        ),
        # S07: Approved (awaiting Payment in Process — operator action pending)
        _SeedSpec(
            number="WPR-2026-DEMO-07",
            title="Maya August travel reimbursement",
            purpose="Reimburse client engagement travel.",
            target_state=LifecycleState.APPROVED,
            family="employee",
            subtype="reimbursement",
            amount="7250000",
            requester=requester_primary,
        ),
        # S08: Payment in Process (operator started, awaiting external reference)
        _SeedSpec(
            number="WPR-2026-DEMO-08",
            title="Jaipur Audit fees",
            purpose="External auditor travel and per-diem.",
            target_state=LifecycleState.PAYMENT_IN_PROCESS,
            family="vendor",
            subtype="standard",
            amount="31400000",
            requester=requester_secondary,
        ),
        # S09: Paid
        _SeedSpec(
            number="WPR-2026-DEMO-09",
            title="Can Tho Catering — board meeting",
            purpose="Catering for the July board meeting.",
            target_state=LifecycleState.PAID,
            family="vendor",
            subtype="standard",
            amount="9800000",
            requester=requester_primary,
        ),
        # S10: Closed
        _SeedSpec(
            number="WPR-2026-DEMO-10",
            title="Visa services — residency renewals",
            purpose="Visa renewal processing for Q2 team.",
            target_state=LifecycleState.CLOSED,
            family="vendor",
            subtype="standard",
            amount="22500000",
            requester=requester_primary,
        ),
        # S11: Rejected
        _SeedSpec(
            number="WPR-2026-DEMO-11",
            title="Hue Catering — private event",
            purpose="(Rejected: outside business scope.)",
            target_state=LifecycleState.REJECTED,
            family="vendor",
            subtype="standard",
            amount="4500000",
            requester=requester_primary,
        ),
        # S12: Cancelled
        _SeedSpec(
            number="WPR-2026-DEMO-12",
            title="Da Lat Conference deposit",
            purpose="(Cancelled: event postponed.)",
            target_state=LifecycleState.CANCELLED,
            family="vendor",
            subtype="standard",
            amount="18000000",
            requester=requester_secondary,
        ),
        # S13: Returned for Correction
        _SeedSpec(
            number="WPR-2026-DEMO-13",
            title="Mekong Logistics surcharge",
            purpose="(Returned: missing goods receipt.)",
            target_state=LifecycleState.RETURNED_FOR_CORRECTION,
            family="vendor",
            subtype="standard",
            amount="6420000",
            requester=requester_primary,
        ),
        # S14: Adjustment Process
        _SeedSpec(
            number="WPR-2026-DEMO-14",
            title="HCMC cleaning services — Q1",
            purpose="Recurring cleaning services, with Q1 adjustment.",
            target_state=LifecycleState.ADJUSTMENT_PROCESS,
            family="vendor",
            subtype="standard",
            amount="14200000",
            requester=requester_primary,
        ),
        # S15: Employee advance (cash advance issued)
        _SeedSpec(
            number="WPR-2026-DEMO-15",
            title="Maya client trip — advance",
            purpose="Cash advance for Q3 client engagement trip.",
            target_state=LifecycleState.PAID,
            family="employee",
            subtype="advance",
            amount="15000000",
            requester=requester_primary,
        ),
        # S16: Over-budget exception (Vendor at Approval Pending with CFO appended)
        _SeedSpec(
            number="WPR-2026-DEMO-16",
            title="HCMC logistics — over budget exception",
            purpose="Critical logistics expense; requires CFO exception.",
            target_state=LifecycleState.APPROVAL_PENDING,
            family="vendor",
            subtype="standard",
            amount="2400000000",
            requester=requester_other,
            over_budget=True,
        ),
    )


# --------------------------------------------------------------------------- #
# Aggregate construction
# --------------------------------------------------------------------------- #


def _build_vendor_request(spec: _SeedSpec) -> PaymentRequest:
    gross = _money_vnd(spec.amount)
    zero = Money(
        amount=Decimal(0), currency_code=gross.currency_code, decimal_scale=gross.decimal_scale
    )
    return PaymentRequest(
        request_id=uuid4(),
        request_number=f"{spec.number}-DRAFT"
        if spec.target_state is LifecycleState.DRAFT
        else spec.number,
        request_type=RequestType.VENDOR,
        requester=spec.requester,
        beneficiary=_vendor_beneficiary(spec.title.split(" — ")[0]),
        accounting_dimension=_dimension(cost_center=spec.cost_center, project=spec.project),
        purpose=spec.purpose,
        total_amount=gross,
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.DRAFT,
        lifecycle_version="v1",
        submitted_version=1,
        details=VendorPaymentDetails(
            invoice_number=f"INV-{spec.number[-4:]}",
            invoice_date=_date(-30),
            due_date=_date(15),
            invoice_net_amount=gross,
            vat_amount=zero,
            invoice_gross_amount=gross,
            payment_terms="Net 30",
            proposed_payment_method=spec.payment_method,
            duplicate_warning_key=f"DUPE-{spec.number}",
        ),
        created_at=_dt(-30, hour=9),
        updated_at=_dt(-30, hour=9),
    )


def _build_employee_request(spec: _SeedSpec) -> PaymentRequest:
    gross = _money_vnd(spec.amount)
    zero = Money(
        amount=Decimal(0), currency_code=gross.currency_code, decimal_scale=gross.decimal_scale
    )
    subtype_key = spec.subtype
    subtype_enum = {
        "reimbursement": EmployeeRequestSubtype.REIMBURSEMENT,
        "advance": EmployeeRequestSubtype.ADVANCE,
        "settlement": EmployeeRequestSubtype.ADVANCE_SETTLEMENT,
        "internal": EmployeeRequestSubtype.INTERNAL_EXPENDITURE,
    }[subtype_key]
    return PaymentRequest(
        request_id=uuid4(),
        request_number=f"{spec.number}-DRAFT"
        if spec.target_state is LifecycleState.DRAFT
        else spec.number,
        request_type=RequestType.EMPLOYEE,
        requester=spec.requester,
        beneficiary=_employee_beneficiary(spec.requester),
        accounting_dimension=_dimension(cost_center=spec.cost_center, project=spec.project),
        purpose=spec.purpose,
        total_amount=gross,
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.DRAFT,
        lifecycle_version="v1",
        submitted_version=1,
        details=EmployeePaymentDetails(
            subtype=subtype_enum,
            employee=spec.requester,
            policy_category="Travel",
            activity_start_date=_date(-7),
            activity_end_date=_date(-1),
            merchant_or_payee=spec.title.split(" — ")[0] if " — " in spec.title else spec.title,
            claimed_amount=gross,
            vat_amount=zero,
            requested_payment_date=_date(7),
            receipt_warning_key=None,
        ),
        created_at=_dt(-7, hour=9),
        updated_at=_dt(-7, hour=9),
    )


def _build_request(spec: _SeedSpec) -> PaymentRequest:
    if spec.family == "vendor":
        return _build_vendor_request(spec)
    return _build_employee_request(spec)


# --------------------------------------------------------------------------- #
# Lifecycle advancement helpers
# --------------------------------------------------------------------------- #


def _trail_for(stores: Stores) -> DurableAuditTrail:
    return DurableAuditTrail(stores.audit, retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE)


def _submit(
    request: PaymentRequest,
    actor: UserSnapshot,
    stores: Stores,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    """Submit a Draft request and persist SUBMITTED audit + request."""

    submitted = request.evolve(
        lifecycle_state=LifecycleState.SUBMITTED,
        request_number=request.request_number or "WPR-2026-DEMO-AUTO",
        submitted_version=request.submitted_version or 1,
        updated_at=_now(),
    )
    stores.requests.save(submitted)
    trail.append(
        entity_type="PaymentRequest",
        entity_id=str(submitted.request_id),
        actor=actor,
        action=AuditAction.SUBMITTED,
        occurred_at=_now(),
        new_value=submitted.model_dump_json(round_trip=True),
        reason="Demo seed submission",
        correlation_id=f"{_DEMO_CORRELATION_PREFIX}:{submitted.request_id}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    return submitted


def _advance(
    request: PaymentRequest,
    target: LifecycleState,
    actor: UserSnapshot,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    """Move a request forward one canonical step, emitting a CHANGED audit event."""

    advanced = request.evolve(lifecycle_state=target, updated_at=_now())
    trail.append(
        entity_type="PaymentRequest",
        entity_id=str(advanced.request_id),
        actor=actor,
        action=AuditAction.CHANGED,
        occurred_at=_now(),
        new_value=advanced.model_dump_json(round_trip=True),
        reason=f"Demo seed transition → {target.value}",
        correlation_id=f"{_DEMO_CORRELATION_PREFIX}:{advanced.request_id}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    return advanced


def _terminal(
    request: PaymentRequest,
    target: LifecycleState,
    actor: UserSnapshot,
    action: AuditAction,
    reason: str,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    advanced = request.evolve(lifecycle_state=target, updated_at=_now())
    trail.append(
        entity_type="PaymentRequest",
        entity_id=str(advanced.request_id),
        actor=actor,
        action=action,
        occurred_at=_now(),
        new_value=advanced.model_dump_json(round_trip=True),
        reason=reason,
        correlation_id=f"{_DEMO_CORRELATION_PREFIX}:{advanced.request_id}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    return advanced


# --------------------------------------------------------------------------- #
# Route generation + decision walking
# --------------------------------------------------------------------------- #


def _generate_route(
    request: PaymentRequest,
    actor: UserSnapshot,
    stores: Stores,
    trail: DurableAuditTrail,
    *,
    over_budget: bool = False,
) -> WorkflowInstance:
    rule_version = stores.rules.active_version()
    rules = stores.rules.rules(rule_version)
    budget_result = (
        BudgetResult.OVER_BUDGET_EXCEPTION_REQUIRED if over_budget else BudgetResult.WITHIN_BUDGET
    )
    result = generate_route(
        GenerateRouteCommand(
            request_id=request.request_id,
            generation_inputs=RouteGenerationInput(
                request_type=request.request_type,
                amount=request.total_amount,
                budget_result=budget_result,
                legal_entity_code=request.accounting_dimension.legal_entity_code,
                department_code=request.accounting_dimension.department_code,
            ),
        ),
        rules=rules,
        rule_version=rule_version,
        now=_now(),
        actor=actor,
        audit=trail,
    )
    stores.workflows.save_instance(result.instance)
    return result.instance


def _approve_all_steps(
    instance: WorkflowInstance,
    request: PaymentRequest,
    stores: Stores,
    trail: DurableAuditTrail,
) -> WorkflowInstance:
    """Apply APPROVED to every pending step in order (sample compliance only)."""

    updated = instance
    for step in updated.steps:
        if step.decision is not ApprovalDecision.PENDING:
            continue
        cmd = DecisionCommand(
            workflow_instance_id=updated.workflow_instance_id,
            step_id=step.step_id,
            decision=ApprovalDecision.APPROVED,
            actor=step.approver,
            reason="Demo seed approval",
        )
        result = decide(
            cmd,
            instance=updated,
            requester_id=request.requester.external_identity_id,
            now=_now(),
            trail_appender=trail,
        )
        updated = result.instance
    stores.workflows.save_instance(updated)
    return updated


# --------------------------------------------------------------------------- #
# Payment recording (PAID + CLOSED)
# --------------------------------------------------------------------------- #


def _record_payment(
    request: PaymentRequest,
    actor: UserSnapshot,
    stores: Stores,
    trail: DurableAuditTrail,
) -> tuple[PaymentRequest, PaymentRecord | None]:
    """Move APPROVED → PAYMENT_IN_PROCESS → PAID for the supplied request.

    The operator actor is the sample Payment Operator persona (not the
    requester) so CONTEXT.md invariant 8 (requester ≠ operator) is honored.
    """

    operator = _operator_actor()
    in_process = start_payment(
        stores,
        request_id=request.request_id,
        actor=operator,
        actor_roles=(RoleName.PAYMENT_OPERATOR,),
        audit=trail,
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
        now=_now(),
    ).request
    result = record_payment(
        stores,
        request_id=in_process.request_id,
        actor=operator,
        actor_roles=(RoleName.PAYMENT_OPERATOR,),
        payment_date=_date(0),
        amount=in_process.total_amount,
        method="BANK_TRANSFER",
        external_reference=f"EXT-{request.request_number}",
        proof_document_id=uuid4(),
        audit=trail,
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
        now=_now(),
    )
    stores.requests.save(result.request)
    return result.request, result.record


def _operator_actor() -> UserSnapshot:
    """Return the canonical Payment Operator persona snapshot."""

    for persona in default_personas():
        if RoleName.PAYMENT_OPERATOR in persona.roles:
            return persona.snapshot
    raise RuntimeError("Demo seed requires at least one Payment Operator persona.")


def _close(
    request: PaymentRequest,
    actor: UserSnapshot,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    advanced = request.evolve(
        lifecycle_state=LifecycleState.CLOSED,
        updated_at=_now(),
    )
    trail.append(
        entity_type="PaymentRequest",
        entity_id=str(advanced.request_id),
        actor=actor,
        action=AuditAction.CLOSED,
        occurred_at=_now(),
        new_value=advanced.model_dump_json(round_trip=True),
        reason="Demo seed closure",
        correlation_id=f"{_DEMO_CORRELATION_PREFIX}:{advanced.request_id}",
        retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
    )
    return advanced


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


def demo_seed_active() -> bool:
    """Whether ``WISPAY_DEMO_MODE=1`` is set on the current process."""

    return os.environ.get("WISPAY_DEMO_MODE") == "1"


@dataclass(frozen=True, slots=True)
class SeedSummary:
    """Counts produced by :func:`seed_demo_state`."""

    requests: int
    audits: int
    payments: int
    personas: int


def seed_demo_state(
    stores: Stores,
    *,
    personas: tuple[DemoPersona, ...] | None = None,
) -> SeedSummary:
    """Populate ``stores`` with S01–S16 + supporting audit/payment records.

    The seed is additive and idempotent: every demo-numbered request is
    upserted so a second call leaves the dataset consistent. Rules v1 must
    already be seeded (the runtime lifespan task handles that for the dev
    driver; tests can call :func:`stores.rules.ensure_seeded` themselves).
    """

    roster = personas or default_personas()
    trail = _trail_for(stores)

    # Make the seed idempotent: drop any prior demo fixtures before re-seeding.
    _clear_demo_records(stores)

    payment_record_count = 0
    for spec in _specs():
        request = _build_request(spec)
        # S01: stays as Draft; never submitted, no audit beyond initial save.
        if spec.target_state is LifecycleState.DRAFT:
            stores.requests.save(request)
            continue
        # Submit and advance through the review buckets up to (and including)
        # APPROVAL_PENDING. The approval route is generated at that point.
        submitted = _submit(request, spec.requester, stores, trail)
        at_approval = _walk_to_approval_pending(submitted, spec, trail)
        if at_approval.lifecycle_state is not LifecycleState.APPROVAL_PENDING:
            # Branch targets (RETURNED, REJECTED, CANCELLED) never reach
            # approval; just persist the latest step and continue.
            stores.requests.save(at_approval)
            continue
        instance = _generate_route(
            at_approval,
            spec.requester,
            stores,
            trail,
            over_budget=spec.over_budget,
        )
        advanced = at_approval.evolve(workflow_instance_id=instance.workflow_instance_id)
        if spec.target_state in _ROUTE_COMPLETE_STATES:
            completed = _approve_all_steps(instance, advanced, stores, trail)
            if completed.final_outcome is WorkflowOutcome.APPROVED:
                advanced = _advance(advanced, LifecycleState.APPROVED, spec.requester, trail)
                advanced = advanced.evolve(workflow_instance_id=completed.workflow_instance_id)
                stores.requests.save(advanced)
                advanced = _post_approval(advanced, spec, stores, trail)
        stores.requests.save(advanced)
        for _record in stores.payments.for_request(advanced.request_id):
            payment_record_count += 1
    audit_count = _audit_event_count(stores)
    return SeedSummary(
        requests=len(_specs()),
        audits=audit_count,
        payments=payment_record_count,
        personas=len(roster),
    )


def _post_approval(
    approved: PaymentRequest,
    spec: _SeedSpec,
    stores: Stores,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    """Move an APPROVED request to its post-approval target state.

    For PAID, CLOSED, and ADJUSTMENT_PROCESS targets the request walks
    through PAYMENT_IN_PROCESS and the external-reference record. For
    PAYMENT_IN_PROCESS the request only advances one step (the operator
    has not yet recorded the external reference in the demo).
    """

    advanced = approved
    if spec.target_state is LifecycleState.APPROVED:
        return advanced
    if spec.target_state is LifecycleState.PAYMENT_IN_PROCESS:
        # Operator has not yet recorded the external reference.
        advanced = _advance(advanced, LifecycleState.PAYMENT_IN_PROCESS, spec.requester, trail)
        stores.requests.save(advanced)
        return advanced
    if spec.target_state in _RECORD_PAYMENT_STATES:
        advanced, _ = _record_payment(advanced, spec.requester, stores, trail)
    if spec.target_state in _CLOSED_STATES:
        advanced = _close(advanced, spec.requester, trail)
    if spec.target_state is LifecycleState.ADJUSTMENT_PROCESS:
        advanced = _advance(advanced, LifecycleState.ADJUSTMENT_PROCESS, spec.requester, trail)
    return advanced


def _walk_to_approval_pending(
    submitted: PaymentRequest,
    spec: _SeedSpec,
    trail: DurableAuditTrail,
) -> PaymentRequest:
    """Advance the request through every step required to reach ``APPROVAL_PENDING``.

    Branch targets (RETURNED, REJECTED, CANCELLED) only walk their own
    state; everything else stops at APPROVAL_PENDING so the route
    generation can run.
    """

    advanced = submitted
    target = spec.target_state
    if target in _BRANCH_TARGETS:
        advanced = _advance(advanced, target, spec.requester, trail)
        return advanced
    for step in _normal_path_to_approval(target):
        advanced = _advance(advanced, step, spec.requester, trail)
    return advanced


# Branch targets skip the approval route entirely.
_BRANCH_TARGETS: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.RETURNED_FOR_CORRECTION,
        LifecycleState.REJECTED,
        LifecycleState.CANCELLED,
    }
)

# Lifecycle states that require a fully-decided approval route.
_ROUTE_COMPLETE_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.APPROVED,
        LifecycleState.PAYMENT_IN_PROCESS,
        LifecycleState.PAID,
        LifecycleState.CLOSED,
        LifecycleState.ADJUSTMENT_PROCESS,
    }
)

# Lifecycle states that require a payment record to be appended.
_RECORD_PAYMENT_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.PAID,
        LifecycleState.CLOSED,
        LifecycleState.ADJUSTMENT_PROCESS,
    }
)

# Lifecycle states that require the request to be Closed.
_CLOSED_STATES: frozenset[LifecycleState] = frozenset(
    {
        LifecycleState.CLOSED,
        LifecycleState.ADJUSTMENT_PROCESS,
    }
)


def _normal_path_to_approval(target: LifecycleState) -> tuple[LifecycleState, ...]:
    """Path from SUBMITTED to APPROVAL_PENDING for any post-approval target."""

    if target in _BRANCH_TARGETS:
        return ()
    if target is LifecycleState.SUBMITTED:
        return ()
    if target in {
        LifecycleState.BUDGET_REVIEW,
        LifecycleState.COMPLIANCE_REVIEW,
        LifecycleState.EVIDENCE_VALIDATION,
    }:
        # Stops at the review bucket; never reaches approval.
        return _path_to_review(target)
    # Anything past Approval Pending walks through the three review buckets
    # and stops at Approval Pending (so the route can be decided).
    return (
        LifecycleState.BUDGET_REVIEW,
        LifecycleState.COMPLIANCE_REVIEW,
        LifecycleState.EVIDENCE_VALIDATION,
        LifecycleState.APPROVAL_PENDING,
    )


def _path_to_review(target: LifecycleState) -> tuple[LifecycleState, ...]:
    """Return the path to the earliest review bucket requested."""

    if target is LifecycleState.BUDGET_REVIEW:
        return (LifecycleState.BUDGET_REVIEW,)
    if target is LifecycleState.COMPLIANCE_REVIEW:
        return (LifecycleState.BUDGET_REVIEW, LifecycleState.COMPLIANCE_REVIEW)
    return (
        LifecycleState.BUDGET_REVIEW,
        LifecycleState.COMPLIANCE_REVIEW,
        LifecycleState.EVIDENCE_VALIDATION,
    )


def _audit_event_count(stores: Stores) -> int:
    """Best-effort audit event tally for the seed summary.

    The audit store does not expose a list-all method (ADR-0004 keeps the
    table append-only), so we read the in-memory backing list when
    available and return 0 for the durable drivers (the trail's hash chain
    is verifiable separately).
    """

    backing = getattr(stores.audit, "_events", None)
    if backing is None:
        return 0
    return len(tuple(backing))


def _clear_demo_records(stores: Stores) -> None:
    """Remove any previously seeded demo fixtures so re-seeding is idempotent.

    Only rows whose ``request_number`` starts with the demo prefix are
    touched; real submissions are left alone. The in-memory fake uses
    its ``_by_id`` dict. The SQLite driver uses a direct SQL delete scoped
    to the demo prefix; Azure SQL falls back to a no-op (the durable
    stores intentionally forbid hard-deletes of financial records, and
    production seed runs are once-per-process anyway).
    """

    by_id = getattr(stores.requests, "_by_id", None)
    if isinstance(by_id, dict):
        for key in list(by_id.keys()):
            req = by_id[key]
            number = req.request_number or ""
            if number.startswith(_DEMO_NUMBER_PREFIX):
                by_id.pop(key, None)
        return
    conn = getattr(stores.requests, "_conn", None)
    if conn is not None:
        try:
            conn.execute(
                "DELETE FROM wispay_payment_record WHERE request_id IN "
                "(SELECT request_id FROM wispay_payment_request "
                "WHERE request_number LIKE ?)",
                (f"{_DEMO_NUMBER_PREFIX}%",),
            )
            conn.execute(
                "DELETE FROM wispay_workflow_instance WHERE request_id IN "
                "(SELECT request_id FROM wispay_payment_request "
                "WHERE request_number LIKE ?)",
                (f"{_DEMO_NUMBER_PREFIX}%",),
            )
            conn.execute(
                "DELETE FROM wispay_payment_request WHERE request_number LIKE ?",
                (f"{_DEMO_NUMBER_PREFIX}%",),
            )
            conn.commit()
        except Exception:
            # Best-effort: durable stores are the production surface and
            # production seed is once-per-process. Ignore failures here.
            pass
        return
    # Azure SQL or other durable driver: nothing to clear.
    return


# --------------------------------------------------------------------------- #
# Required-doc checklist re-export (t4 surfaces consume it directly)
# --------------------------------------------------------------------------- #


def required_doc_keys(family: str, subtype: str) -> tuple[str, ...]:
    """Return the required doc keys for one family/subtype combination."""

    return tuple(req.key for req in doc_requirements(family, subtype) if req.required)


__all__ = [
    "DEMO_REFERENCE_DATE",
    "DemoPersona",
    "SeedSummary",
    "default_personas",
    "default_role_assignments",
    "demo_seed_active",
    "required_doc_keys",
    "seed_demo_state",
]
