"""Payment recording service.

Implements CONTEXT.md invariants 7, 8, 9, 10 for the operator-driven recording
flow. WisPay records external payment completion; it never initiates money
movement. The service enforces:

* **Invariant 7:** only ``APPROVED`` requests enter ``PAYMENT_IN_PROCESS``.
* **Invariant 8:** only authorized Finance / Payment Operator roles may
  record payment completion.
* **Invariant 9:** the recorded amount must equal the approved amount (an
  absolute equality guardrail, not a float comparison).
* **Invariant 10:** payment records are append-only — no UPDATE / DELETE.

Authorization is checked by role, not by trusted caller-supplied role names
(ADR-0007 / ADR-0008). The service writes one ``PAYMENT_UPDATED`` audit
event per recording and bumps the request lifecycle forward only on the
terminal ``record`` path.

Pure Python per ADR-0005: no Reflex imports. Operates against the ``Stores``
Protocol so the same code runs against Azure SQL and SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from WisPay.models import (
    AuditAction,
    LifecycleState,
    Money,
    PaymentReconciliationState,
    PaymentRecord,
    UserSnapshot,
)
from WisPay.models.enums import RoleName

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

    from WisPay.models import PaymentRequest
    from WisPay.services.audit_trail import InMemoryAuditTrail
    from WisPay.services.repositories import Stores
    from WisPay.services.sql_repositories import DurableAuditTrail


class PaymentRecordingError(ValueError):
    """Base class for payment recording guard failures."""


class RequestNotApprovedError(PaymentRecordingError):
    """Operation requires the request to be in the APPROVED state."""


class RequestNotInProcessError(PaymentRecordingError):
    """``start`` only applies to APPROVED; ``record`` only to PAYMENT_IN_PROCESS."""


class AmountMismatchError(PaymentRecordingError):
    """Recorded amount must equal the approved amount (invariant 9)."""


class UnauthorizedOperatorError(PaymentRecordingError):
    """Only authorized Finance / Payment Operator roles may record payment."""


class MissingExternalReferenceError(PaymentRecordingError):
    """External payment reference is required when recording payment."""


#: Roles allowed to start / record / close payment operations (ADR-0007).
PAYMENT_OPERATOR_ROLES: frozenset[RoleName] = frozenset(
    {
        RoleName.PAYMENT_OPERATOR,
        RoleName.FINANCE_REVIEWER,
        RoleName.SYSTEM_ADMINISTRATOR,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _has_any_role(actor_roles: Iterable[RoleName], allowed: frozenset[RoleName]) -> bool:
    """Return whether any of the actor's roles intersects ``allowed``."""
    return any(role in allowed for role in actor_roles)


def _require_operator_roles(actor_roles: Iterable[RoleName], allowed: frozenset[RoleName]) -> None:
    """Deny-by-default role gate for start / record / close.

    An un-tagged actor (no roles attached) is rejected so the guard cannot
    be silently bypassed by callers that drop the roles argument.
    """
    roles = tuple(actor_roles)
    if not roles:
        raise UnauthorizedOperatorError(
            "The actor has no roles attached; Payment Operator authorization cannot be checked."
        )
    if not _has_any_role(roles, allowed):
        raise UnauthorizedOperatorError(
            "Only an authorized Finance / Payment Operator may record payment completion."
        )


def _require_external_reference(reference: str | None) -> None:
    if reference is None or not reference.strip():
        raise MissingExternalReferenceError(
            "External payment reference is required (ADR-0004 cross-cutting rule 5)."
        )


@dataclass(frozen=True, slots=True)
class StartPaymentResult:
    """Updated request plus the lifecycle-bumping audit event."""

    request: PaymentRequest
    audit_event: object


@dataclass(frozen=True, slots=True)
class RecordPaymentResult:
    """Recorded payment, updated request state, and appended audit event."""

    record: PaymentRecord
    request: PaymentRequest
    audit_event: object


def start_payment(
    stores: Stores,
    *,
    request_id: UUID,
    actor: UserSnapshot,
    actor_roles: Iterable[RoleName],
    audit: InMemoryAuditTrail | DurableAuditTrail,
    retention_policy_id: UUID,
    now: datetime | None = None,
) -> StartPaymentResult:
    """Transition APPROVED → PAYMENT_IN_PROCESS.

    CONTEXT.md invariants 7 (only approved requests enter payment
    processing) and 8 (operator authorization) are enforced here.
    """
    timestamp = now or _now()
    request = stores.requests.get(request_id)
    if request is None:
        raise RequestNotApprovedError(f"Payment Request {request_id} not found.")
    if request.lifecycle_state is not LifecycleState.APPROVED:
        raise RequestNotInProcessError(
            "`start_payment` requires the request to be in APPROVED state."
        )
    _require_operator_roles(actor_roles, PAYMENT_OPERATOR_ROLES)
    if audit is None:
        raise PaymentRecordingError(
            "An audit appender is required so PAYMENT_IN_PROCESS transitions are tamper-evident."
        )
    advanced = request.evolve(
        lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS,
        lifecycle_version=request.lifecycle_version,
        updated_at=timestamp,
    )
    stores.requests.save(advanced)
    event = audit.append(
        entity_type="PaymentRequest",
        entity_id=str(advanced.request_id),
        actor=actor,
        action=AuditAction.CHANGED,
        occurred_at=timestamp,
        new_value=advanced.model_dump_json(round_trip=True),
        reason="Payment in Process",
        correlation_id=f"start-payment:{advanced.request_id}",
        retention_policy_id=retention_policy_id,
    )
    return StartPaymentResult(request=advanced, audit_event=event)


def record_payment(
    stores: Stores,
    *,
    request_id: UUID,
    actor: UserSnapshot,
    actor_roles: Iterable[RoleName],
    payment_date: date,
    amount: Money,
    method: str,
    external_reference: str,
    proof_document_id: UUID,
    audit: InMemoryAuditTrail | DurableAuditTrail,
    retention_policy_id: UUID,
    accounting_reference: str | None = None,
    now: datetime | None = None,
) -> RecordPaymentResult:
    """Append a PaymentRecord and advance the request to ``PAID``.

    Invariants enforced:

    * **7 & 8:** the request must be in ``PAYMENT_IN_PROCESS``; the actor must
      hold a Payment Operator / Finance role.
    * **9:** the recorded ``amount`` must equal the approved
      ``total_amount`` (currency-aware equality via :class:`Money`).
    * **10:** the new ``PaymentRecord`` is appended via
      ``stores.payments.save``; never updated or deleted.
    """
    timestamp = now or _now()
    request = stores.requests.get(request_id)
    if request is None:
        raise RequestNotInProcessError(f"Payment Request {request_id} not found.")
    if request.lifecycle_state is not LifecycleState.PAYMENT_IN_PROCESS:
        raise RequestNotInProcessError(
            "Payment can only be recorded while the request is in PAYMENT_IN_PROCESS."
        )
    _require_operator_roles(actor_roles, PAYMENT_OPERATOR_ROLES)
    _require_external_reference(external_reference)
    if amount != request.total_amount:
        raise AmountMismatchError(
            f"Recorded amount ({amount.amount} {amount.currency_code}, scale "
            f"{amount.decimal_scale}) does not equal the approved amount "
            f"({request.total_amount.amount} {request.total_amount.currency_code}, "
            f"scale {request.total_amount.decimal_scale})."
        )
    if actor.external_identity_id == request.requester.external_identity_id:
        raise UnauthorizedOperatorError(
            "The requester cannot record payment completion for their own request."
        )
    if audit is None:
        raise PaymentRecordingError(
            "An audit appender is required so recorded payments are tamper-evident."
        )
    record = PaymentRecord(
        payment_record_id=uuid4(),
        request_id=request_id,
        payment_date=payment_date,
        amount=amount,
        method=method,
        external_reference=external_reference,
        accounting_reference=accounting_reference,
        proof_document_id=proof_document_id,
        operator=actor,
        reconciliation_state=PaymentReconciliationState.PENDING,
        recorded_at=timestamp,
    )
    stores.payments.save(record)
    advanced = request.evolve(
        lifecycle_state=LifecycleState.PAID,
        updated_at=timestamp,
        payment_record_ids=(*request.payment_record_ids, record.payment_record_id),
    )
    stores.requests.save(advanced)
    event = audit.append(
        entity_type="PaymentRecord",
        entity_id=str(record.payment_record_id),
        actor=actor,
        action=AuditAction.PAYMENT_UPDATED,
        occurred_at=timestamp,
        new_value=record.model_dump_json(round_trip=True),
        reason=f"Payment recorded externally (reference {external_reference})",
        correlation_id=str(request_id),
        retention_policy_id=retention_policy_id,
    )
    return RecordPaymentResult(record=record, request=advanced, audit_event=event)
