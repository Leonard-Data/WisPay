from enum import StrEnum


class LifecycleState(StrEnum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    BUDGET_REVIEW = "Budget Review"
    COMPLIANCE_REVIEW = "Compliance Review"
    EVIDENCE_VALIDATION = "Evidence Validation"
    APPROVAL_PENDING = "Approval Pending"
    APPROVED = "Approved"
    PAYMENT_IN_PROCESS = "Payment in Process"
    PAID = "Paid"
    CLOSED = "Closed"
    RETURNED_FOR_CORRECTION = "Returned for Correction"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    ADJUSTMENT_PROCESS = "Adjustment Process"


type LifecycleTransition = tuple[LifecycleState, LifecycleState]

NORMAL_TRANSITIONS: frozenset[LifecycleTransition] = frozenset(
    {
        (LifecycleState.DRAFT, LifecycleState.SUBMITTED),
        (LifecycleState.SUBMITTED, LifecycleState.BUDGET_REVIEW),
        (LifecycleState.BUDGET_REVIEW, LifecycleState.COMPLIANCE_REVIEW),
        (LifecycleState.COMPLIANCE_REVIEW, LifecycleState.EVIDENCE_VALIDATION),
        (LifecycleState.EVIDENCE_VALIDATION, LifecycleState.APPROVAL_PENDING),
        (LifecycleState.APPROVAL_PENDING, LifecycleState.APPROVED),
        (LifecycleState.APPROVED, LifecycleState.PAYMENT_IN_PROCESS),
        (LifecycleState.PAYMENT_IN_PROCESS, LifecycleState.PAID),
        (LifecycleState.PAID, LifecycleState.CLOSED),
    }
)

EXCEPTION_TRANSITIONS: frozenset[LifecycleTransition] = frozenset(
    {
        (LifecycleState.DRAFT, LifecycleState.CANCELLED),
        (LifecycleState.SUBMITTED, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.SUBMITTED, LifecycleState.CANCELLED),
        (LifecycleState.BUDGET_REVIEW, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.BUDGET_REVIEW, LifecycleState.REJECTED),
        (LifecycleState.COMPLIANCE_REVIEW, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.COMPLIANCE_REVIEW, LifecycleState.REJECTED),
        (LifecycleState.EVIDENCE_VALIDATION, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.EVIDENCE_VALIDATION, LifecycleState.REJECTED),
        (LifecycleState.APPROVAL_PENDING, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.APPROVAL_PENDING, LifecycleState.REJECTED),
        (LifecycleState.RETURNED_FOR_CORRECTION, LifecycleState.SUBMITTED),
        (LifecycleState.RETURNED_FOR_CORRECTION, LifecycleState.CANCELLED),
        (LifecycleState.APPROVED, LifecycleState.CANCELLED),
        (LifecycleState.PAYMENT_IN_PROCESS, LifecycleState.CANCELLED),
        (LifecycleState.PAYMENT_IN_PROCESS, LifecycleState.RETURNED_FOR_CORRECTION),
        (LifecycleState.PAID, LifecycleState.ADJUSTMENT_PROCESS),
        (LifecycleState.CLOSED, LifecycleState.ADJUSTMENT_PROCESS),
    }
)

DECLARED_TRANSITIONS = NORMAL_TRANSITIONS | EXCEPTION_TRANSITIONS


def is_declared_transition(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    """Return whether the canonical state machine declares this transition.

    Authorization and transition guards remain service-layer responsibilities.
    """

    return (from_state, to_state) in DECLARED_TRANSITIONS
