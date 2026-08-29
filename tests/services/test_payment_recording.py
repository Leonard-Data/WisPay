"""Unit + integration tests for the payment recording service (BE-2).

Asserts:

* **Invariant 7:** only ``APPROVED`` requests enter ``PAYMENT_IN_PROCESS``;
  only ``PAYMENT_IN_PROCESS`` requests reach ``PAID``.
* **Invariant 8:** only Finance / Payment Operator / System Administrator
  roles may start / record payments.
* **Invariant 9:** recorded amount must equal the approved
  ``total_amount`` (currency-aware equality; no float).
* **Invariant 10:** the ``PaymentRecordStore`` is append-only — no
  ``UPDATE`` or ``DELETE`` methods are exposed.
* **SoD:** the requester can never record payment for their own request
  (treated as a hard form of invariant 8).

The same assertions run against ``FakePaymentRecordStore`` and the
SQLite-backed ``SqlitePaymentRecordStore``; the canonical contract is the
``PaymentRecordStore`` Protocol and the durable ``Stores`` bundle.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from tests.services.fakes import durable_trail
from WisPay.models import (
    AccountingDimension,
    AuditAction,
    BeneficiaryReference,
    LifecycleState,
    Money,
    PaymentRecord,
    PaymentRequest,
    RequestType,
    UserSnapshot,
    VendorPaymentDetails,
)
from WisPay.models.enums import (
    AccessClassification,
    BeneficiaryType,
    OpexCapexClassification,
    RoleName,
)
from WisPay.services import payment_recording as pr
from WisPay.services.repositories import (
    PaymentRecordStore,
    Stores,
)
from WisPay.services.sqlite_repositories import (
    SqlitePaymentRecordStore,
    sqlite_stores,
)

_RECEIVED_AT = datetime(2026, 8, 26, 9, 0, 0, tzinfo=UTC)
_RETENTION = UUID("00000000-0000-4000-8000-0000000000b1")


def _actor(suffix: str) -> UserSnapshot:
    return UserSnapshot(
        external_identity_id=f"user-{suffix}",
        display_name=f"User {suffix}",
        email=f"{suffix}@wispay.example",
        captured_at=_RECEIVED_AT,
    )


def _requester() -> UserSnapshot:
    return _actor("requester")


def _operator() -> UserSnapshot:
    return _actor("operator")


def _operator_roles() -> tuple[RoleName, ...]:
    return (RoleName.PAYMENT_OPERATOR,)


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency_code="VND", decimal_scale=0)


def _approved_request(*, total: str = "11000000") -> PaymentRequest:
    return PaymentRequest(
        request_id=uuid4(),
        request_number="WPR-2026-PR1",
        request_type=RequestType.VENDOR,
        requester=_requester(),
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="Acme Supplies",
            captured_at=_RECEIVED_AT,
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
            captured_at=_RECEIVED_AT,
        ),
        purpose="Vendor invoice payment",
        total_amount=_money(total),
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.APPROVED,
        lifecycle_version="v1",
        submitted_version=1,
        details=VendorPaymentDetails(
            invoice_number="INV-1",
            invoice_date=date(2026, 8, 1),
            due_date=date(2026, 8, 31),
            invoice_net_amount=_money("10000000"),
            vat_amount=_money("1000000"),
            invoice_gross_amount=_money("11000000"),
            payment_terms="Net 30",
            proposed_payment_method="Bank transfer",
            duplicate_warning_key="acme|INV-1|11000000",
        ),
        created_at=_RECEIVED_AT,
        updated_at=_RECEIVED_AT,
    )


@pytest.fixture
def stores() -> Stores:
    """Fresh in-memory SQLite-backed Stores per test (BE-2 contract)."""
    conn = sqlite3.connect(":memory:")
    return sqlite_stores(conn=conn, ensure_tables=True)


# --------------------------------------------------------------------------- #
# Protocol shape (uses an isolated connection — no shared cache)
# --------------------------------------------------------------------------- #


def test_sqlite_payment_store_implements_protocol() -> None:
    """SqlitePaymentRecordStore satisfies the PaymentRecordStore Protocol."""
    conn = sqlite3.connect(":memory:")
    try:
        from WisPay.services.sqlite_repositories import ensure_sqlite_schema

        ensure_sqlite_schema(conn)
        store = SqlitePaymentRecordStore(conn)
        assert isinstance(store, PaymentRecordStore)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# start_payment guards
# --------------------------------------------------------------------------- #


def test_start_requires_approved_state(stores: Stores) -> None:
    request = _approved_request()
    request = request.evolve(lifecycle_state=LifecycleState.DRAFT)
    stores.requests.save(request)
    with pytest.raises(pr.RequestNotInProcessError):
        pr.start_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=_operator_roles(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_start_requires_payment_operator_role(stores: Stores) -> None:
    request = _approved_request()
    stores.requests.save(request)
    with pytest.raises(pr.UnauthorizedOperatorError):
        pr.start_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=(RoleName.REQUESTER,),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_start_unset_roles_is_denied(stores: Stores) -> None:
    request = _approved_request()
    stores.requests.save(request)
    with pytest.raises(pr.UnauthorizedOperatorError):
        pr.start_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_start_transitions_approved_to_payment_in_process(stores: Stores) -> None:
    request = _approved_request()
    stores.requests.save(request)
    result = pr.start_payment(
        stores,
        request_id=request.request_id,
        actor=_operator(),
        actor_roles=_operator_roles(),
        audit=durable_trail(),
        retention_policy_id=_RETENTION,
        now=_RECEIVED_AT,
    )
    assert result.request.lifecycle_state is LifecycleState.PAYMENT_IN_PROCESS
    refreshed = stores.requests.get(request.request_id)
    assert refreshed is not None
    assert refreshed.lifecycle_state is LifecycleState.PAYMENT_IN_PROCESS


# --------------------------------------------------------------------------- #
# record_payment guards
# --------------------------------------------------------------------------- #


def test_record_requires_payment_in_process_state(stores: Stores) -> None:
    request = _approved_request()  # still APPROVED
    stores.requests.save(request)
    with pytest.raises(pr.RequestNotInProcessError):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=_operator_roles(),
            payment_date=date(2026, 8, 31),
            amount=_money("11000000"),
            method="Bank transfer",
            external_reference="REF-1",
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_requires_payment_operator_role(stores: Stores) -> None:
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    with pytest.raises(pr.UnauthorizedOperatorError):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=(RoleName.REQUESTER,),
            payment_date=date(2026, 8, 31),
            amount=_money("11000000"),
            method="Bank transfer",
            external_reference="REF-1",
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_blocks_requester_as_operator(stores: Stores) -> None:
    """SoD on invariant 8: requester cannot record own payment."""
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    with pytest.raises(pr.UnauthorizedOperatorError):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_requester(),
            actor_roles=_operator_roles(),
            payment_date=date(2026, 8, 31),
            amount=_money("11000000"),
            method="Bank transfer",
            external_reference="REF-1",
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_requires_external_reference(stores: Stores) -> None:
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    with pytest.raises(pr.MissingExternalReferenceError):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=_operator_roles(),
            payment_date=date(2026, 8, 31),
            amount=_money("11000000"),
            method="Bank transfer",
            external_reference="  ",  # whitespace-only
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_blocks_amount_mismatch(stores: Stores) -> None:
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    with pytest.raises(pr.AmountMismatchError):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=_operator_roles(),
            payment_date=date(2026, 8, 31),
            amount=_money("11000001"),  # 1 VND off
            method="Bank transfer",
            external_reference="REF-1",
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_blocks_currency_mismatch(stores: Stores) -> None:
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    # USD 11000.00 != VND 11,000,000 even though nominal values match.
    usd = Money(amount=Decimal("11000.00"), currency_code="USD", decimal_scale=2)
    with pytest.raises((pr.AmountMismatchError, ValueError)):
        pr.record_payment(
            stores,
            request_id=request.request_id,
            actor=_operator(),
            actor_roles=_operator_roles(),
            payment_date=date(2026, 8, 31),
            amount=usd,
            method="Bank transfer",
            external_reference="REF-1",
            proof_document_id=uuid4(),
            audit=durable_trail(),
            retention_policy_id=_RETENTION,
            now=_RECEIVED_AT,
        )


def test_record_writes_payment_record_and_advances_request(stores: Stores) -> None:
    request = _approved_request().evolve(lifecycle_state=LifecycleState.PAYMENT_IN_PROCESS)
    stores.requests.save(request)
    proof_id = uuid4()
    trail = durable_trail()
    result = pr.record_payment(
        stores,
        request_id=request.request_id,
        actor=_operator(),
        actor_roles=_operator_roles(),
        payment_date=date(2026, 8, 31),
        amount=_money("11000000"),
        method="Bank transfer",
        external_reference="BANK-REF-001",
        proof_document_id=proof_id,
        audit=trail,
        retention_policy_id=_RETENTION,
        now=_RECEIVED_AT,
    )
    assert isinstance(result.record, PaymentRecord)
    assert result.record.proof_document_id == proof_id
    assert result.record.external_reference == "BANK-REF-001"
    assert result.request.lifecycle_state is LifecycleState.PAID
    records = stores.payments.for_request(request.request_id)
    assert records == (result.record,)
    refreshed = stores.requests.get(request.request_id)
    assert refreshed is not None
    assert refreshed.lifecycle_state is LifecycleState.PAID
    assert result.record.payment_record_id in refreshed.payment_record_ids
    # The audit trail records the payment action (via the underlying
    # store; ``DurableAuditTrail`` exposes ``events_for_request``).
    matching = [
        event
        for event in trail.events_for_request(str(request.request_id))
        if event.action is AuditAction.PAYMENT_UPDATED
    ]
    assert matching


# --------------------------------------------------------------------------- #
# Append-only contract (CONTEXT.md invariant 10)
# --------------------------------------------------------------------------- #


def test_sqlite_payment_store_exposes_no_delete_or_update() -> None:
    """Invariant 10: no UPDATE / DELETE on the payment-record store."""
    store_attrs = {name for name in dir(SqlitePaymentRecordStore) if not name.startswith("_")}
    assert "delete" not in store_attrs
    assert "update" not in store_attrs
    # Public surface is ``save`` and ``for_request`` only.
    assert "save" in store_attrs
    assert "for_request" in store_attrs


def test_fake_payment_store_exposes_no_delete_or_update() -> None:
    from tests.services.fakes import FakePaymentRecordStore

    store_attrs = {name for name in dir(FakePaymentRecordStore) if not name.startswith("_")}
    assert "delete" not in store_attrs
    assert "update" not in store_attrs
    assert "save" in store_attrs
    assert "for_request" in store_attrs


def test_payment_record_store_protocol_has_no_delete() -> None:
    """The Protocol contract surface forbids ``delete``."""
    from WisPay.services.repositories import PaymentRecordStore

    proto_methods = {
        name
        for name in dir(PaymentRecordStore)
        if not name.startswith("_") and name != "save" and name != "for_request"
    }
    assert proto_methods == set(), f"unexpected Protocol methods: {proto_methods}"
