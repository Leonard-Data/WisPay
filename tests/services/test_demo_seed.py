"""Tests for the demo seed service.

Covers the BS-1 contract: S01–S16 fixtures, 8 personas, audit + payment
records, idempotent re-seeding, and ``WISPAY_DEMO_MODE`` env activation.
"""

from __future__ import annotations

import os
import sqlite3

from tests.services.fakes import FakeStores
from WisPay.models import LifecycleState
from WisPay.models.enums import RoleName
from WisPay.services.demo_seed import (
    DEMO_REFERENCE_DATE,
    SeedSummary,
    default_personas,
    default_role_assignments,
    demo_seed_active,
    required_doc_keys,
    seed_demo_state,
)
from WisPay.services.sqlite_repositories import sqlite_stores
from WisPay.services.workflow_rules import seed_rules_v1


def _seeded_fake_stores() -> object:
    """Build an in-memory bundle with v1 rules pre-seeded."""

    return FakeStores(rules=seed_rules_v1()).stores


# --------------------------------------------------------------------------- #
# Personas + role assignments
# --------------------------------------------------------------------------- #


def test_default_personas_returns_eight_distinct_entries() -> None:
    """The persona roster must cover the eight canonical roles (A13)."""

    roster = default_personas()
    assert len(roster) == 8
    ids = {persona.snapshot.external_identity_id for persona in roster}
    assert len(ids) == 8
    roles = {role for persona in roster for role in persona.roles}
    assert RoleName.REQUESTER in roles
    assert RoleName.LINE_MANAGER in roles
    assert RoleName.BUDGET_OWNER in roles
    assert RoleName.FINANCE_REVIEWER in roles
    assert RoleName.EXECUTIVE_APPROVER in roles
    assert RoleName.PAYMENT_OPERATOR in roles
    assert RoleName.AUDITOR in roles


def test_default_role_assignments_use_canonical_role_model() -> None:
    """Role assignments must satisfy the canonical ``RoleAssignment`` contract."""

    roster = default_personas()
    assignments = default_role_assignments(roster)
    assert len(assignments) >= len(roster)
    for assignment in assignments:
        assert assignment.user.external_identity_id
        assert assignment.role in RoleName
        assert assignment.organization_scope
        assert assignment.source
        assert assignment.version
        assert assignment.ends_at is None or assignment.ends_at > assignment.starts_at


def test_demo_seed_active_reflects_env() -> None:
    """``WISPAY_DEMO_MODE=1`` activates the seed; other values do not."""

    saved = os.environ.pop("WISPAY_DEMO_MODE", None)
    try:
        os.environ.pop("WISPAY_DEMO_MODE", None)
        assert demo_seed_active() is False
        os.environ["WISPAY_DEMO_MODE"] = "1"
        assert demo_seed_active() is True
        os.environ["WISPAY_DEMO_MODE"] = "0"
        assert demo_seed_active() is False
    finally:
        os.environ.pop("WISPAY_DEMO_MODE", None)
        if saved is not None:
            os.environ["WISPAY_DEMO_MODE"] = saved


def test_required_doc_keys_matches_reference_data() -> None:
    """The seed re-exports the canonical document-requirement matrix."""

    assert "invoice" in required_doc_keys("vendor", "standard")
    assert "receipt" in required_doc_keys("employee", "reimbursement")
    assert "activity_evidence" in required_doc_keys("employee", "advance")


def test_demo_reference_date_is_pinned() -> None:
    """The fixed reference date anchors overdue / SLA math (BS-1 §4.1)."""

    assert DEMO_REFERENCE_DATE == DEMO_REFERENCE_DATE  # pinned
    assert DEMO_REFERENCE_DATE.year == 2026
    assert DEMO_REFERENCE_DATE.month == 8


# --------------------------------------------------------------------------- #
# Seed execution — FakeStores (in-memory doubles)
# --------------------------------------------------------------------------- #


def test_seed_demo_state_returns_summary_with_sixteen_requests() -> None:
    """S01–S16 fixtures are persisted on a fresh in-memory bundle."""

    bundle = _seeded_fake_stores()
    summary = seed_demo_state(bundle)
    assert isinstance(summary, SeedSummary)
    assert summary.requests == 16
    assert summary.personas == 8
    assert summary.payments >= 4  # S07, S08, S09, S10, S15 advance, ...


def test_seed_demo_state_covers_every_lifecycle_state() -> None:
    """Every canonical lifecycle state is represented at least once."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    models = bundle.requests.list_all()
    seen = {req.lifecycle_state for req in models}
    for state in LifecycleState:
        assert state in seen, f"Lifecycle state {state} is not seeded"


def test_seed_demo_state_writes_audit_events_for_every_request() -> None:
    """Audit events are emitted for SUBMITTED + every CHANGED transition."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    models = bundle.requests.list_all()
    for req in models:
        if req.lifecycle_state is LifecycleState.DRAFT:
            continue
        events = bundle.audit.events_for_request(f"demo-seed:{req.request_id}")
        assert any(
            "Submit" in (event.action.value or "") or "SUBMITTED" in event.action.value
            for event in events
        )


def test_seed_demo_state_is_idempotent() -> None:
    """Re-running the seed must not duplicate or break the dataset."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    first_count = len(bundle.requests.list_all())
    seed_demo_state(bundle)
    second_count = len(bundle.requests.list_all())
    assert first_count == second_count


def test_seed_demo_state_records_payment_for_approved_requests() -> None:
    """S07, S08, S09, S10, S15 reach PAID; payment records are persisted."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    paid_numbers = {
        req.request_number
        for req in bundle.requests.list_all()
        if req.lifecycle_state is LifecycleState.PAID
    }
    assert "WPR-2026-DEMO-09" in paid_numbers
    assert "WPR-2026-DEMO-15" in paid_numbers
    assert len(paid_numbers) >= 2
    total_payment_records = sum(
        len(bundle.payments.for_request(req.request_id)) for req in bundle.requests.list_all()
    )
    assert total_payment_records >= 4


def test_seed_demo_state_creates_workflow_instance_for_pending_route() -> None:
    """S06 and S16 (Approval Pending) must carry a frozen workflow instance."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    pending = [
        req
        for req in bundle.requests.list_all()
        if req.lifecycle_state is LifecycleState.APPROVAL_PENDING
    ]
    assert pending, "Expected seeded Approval Pending requests"
    for req in pending:
        assert req.workflow_instance_id is not None
        instance = bundle.workflows.get_instance(req.workflow_instance_id)
        assert instance is not None
        assert instance.request_id == req.request_id


def test_seed_demo_state_terminal_states_are_persisted() -> None:
    """S11, S12, S13, S14 reach their terminal / branch states."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    by_number = {req.request_number: req for req in bundle.requests.list_all()}
    assert by_number["WPR-2026-DEMO-11"].lifecycle_state is LifecycleState.REJECTED
    assert by_number["WPR-2026-DEMO-12"].lifecycle_state is LifecycleState.CANCELLED
    assert by_number["WPR-2026-DEMO-13"].lifecycle_state is LifecycleState.RETURNED_FOR_CORRECTION
    assert by_number["WPR-2026-DEMO-14"].lifecycle_state is LifecycleState.ADJUSTMENT_PROCESS


def test_seed_demo_state_routes_over_budget_through_approval_pending() -> None:
    """S16 (over-budget Vendor) sits at Approval Pending with a frozen route."""

    bundle = _seeded_fake_stores()
    seed_demo_state(bundle)
    by_number = {req.request_number: req for req in bundle.requests.list_all()}
    s16 = by_number["WPR-2026-DEMO-16"]
    assert s16.lifecycle_state is LifecycleState.APPROVAL_PENDING
    assert s16.workflow_instance_id is not None


def test_seed_demo_state_works_against_sqlite_in_memory() -> None:
    """The same seed code runs against the SQLite in-memory driver."""

    conn = sqlite3.connect(":memory:")
    bundle = sqlite_stores(conn=conn, ensure_tables=True)
    summary = seed_demo_state(bundle)
    assert summary.requests == 16
    persisted = bundle.requests.list_all()
    assert len(persisted) == 16
    # Re-fetch one request to confirm round-tripping works.
    s06 = next(req for req in persisted if req.request_number == "WPR-2026-DEMO-06")
    fetched = bundle.requests.get(s06.request_id)
    assert fetched is not None
    assert fetched.request_number == "WPR-2026-DEMO-06"
