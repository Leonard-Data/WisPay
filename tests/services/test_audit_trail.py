"""Hash-chain semantics of the session audit trail."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from WisPay.models import AuditAction, UserSnapshot
from WisPay.services.audit_trail import (
    GENESIS_HASH,
    InMemoryAuditTrail,
    canonical_payload,
    chain_hash,
)

NOW = datetime(2026, 8, 25, 9, 30, tzinfo=UTC)


def actor() -> UserSnapshot:
    return UserSnapshot(
        external_identity_id="actor-1",
        display_name="Test Actor",
        email="actor@example.com",
        captured_at=NOW,
    )


def test_genesis_hash_shape() -> None:
    assert GENESIS_HASH == "0" * 64


def test_canonical_payload_is_key_sorted_and_compact() -> None:
    payload = {"b": 1, "a": "x"}
    assert canonical_payload(payload) == '{"a":"x","b":1}'


def test_chain_hash_is_deterministic_sha256() -> None:
    digest = chain_hash(GENESIS_HASH, "{}")
    assert len(digest) == 64
    assert digest == chain_hash(GENESIS_HASH, "{}")
    assert digest != chain_hash("f" * 64, "{}")


def test_append_links_each_event_to_previous() -> None:
    trail = InMemoryAuditTrail()
    first = trail.append(
        entity_type="PaymentRequest",
        entity_id="r1",
        actor=actor(),
        action=AuditAction.SUBMITTED,
        occurred_at=NOW,
        correlation_id="c1",
        retention_policy_id=UUID(int=1),
    )
    second = trail.append(
        entity_type="PaymentRequest",
        entity_id="r2",
        actor=actor(),
        action=AuditAction.SUBMITTED,
        occurred_at=NOW,
        correlation_id="c2",
        retention_policy_id=UUID(int=1),
    )
    assert first.previous_hash == GENESIS_HASH
    assert second.previous_hash == first.event_hash
    assert trail.verify() is True


def test_verify_detects_tampering() -> None:
    trail = InMemoryAuditTrail()
    event = trail.append(
        entity_type="PaymentRequest",
        entity_id="r1",
        actor=actor(),
        action=AuditAction.SUBMITTED,
        occurred_at=NOW,
        correlation_id="c1",
        retention_policy_id=UUID(int=1),
    )
    tampered = event.model_copy(update={"entity_id": "evil"})
    trail._events[0] = tampered  # noqa: SLF001 - deliberate mutation under test
    assert trail.verify() is False
