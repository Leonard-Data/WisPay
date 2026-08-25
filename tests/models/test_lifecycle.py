from WisPay.models import LifecycleState, is_declared_transition

EXPECTED_STATES = {
    "Draft",
    "Submitted",
    "Budget Review",
    "Compliance Review",
    "Evidence Validation",
    "Approval Pending",
    "Approved",
    "Payment in Process",
    "Paid",
    "Closed",
    "Returned for Correction",
    "Rejected",
    "Cancelled",
    "Adjustment Process",
}


def test_lifecycle_matches_the_canonical_fourteen_states() -> None:
    assert {state.value for state in LifecycleState} == EXPECTED_STATES
    assert "Overdue" not in EXPECTED_STATES


def test_lifecycle_declares_normal_and_exception_transitions() -> None:
    assert is_declared_transition(LifecycleState.DRAFT, LifecycleState.SUBMITTED)
    assert is_declared_transition(
        LifecycleState.APPROVAL_PENDING,
        LifecycleState.RETURNED_FOR_CORRECTION,
    )
    assert is_declared_transition(
        LifecycleState.CLOSED,
        LifecycleState.ADJUSTMENT_PROCESS,
    )


def test_lifecycle_rejects_undeclared_shortcuts() -> None:
    assert not is_declared_transition(LifecycleState.DRAFT, LifecycleState.PAID)
    assert not is_declared_transition(
        LifecycleState.SUBMITTED,
        LifecycleState.APPROVED,
    )
