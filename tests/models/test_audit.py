from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from WisPay.models import AuditAction, AuditEvent, UserSnapshot

NOW = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
HASH = "a" * 64


def actor() -> UserSnapshot:
    return UserSnapshot(
        external_identity_id="entra-user-1",
        display_name="Finance Reviewer",
        email="reviewer@example.com",
        captured_at=NOW,
    )


def test_rejection_audit_event_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="require a reason"):
        AuditEvent(
            audit_event_id=uuid4(),
            entity_type="PaymentRequest",
            entity_id="request-1",
            actor=actor(),
            action=AuditAction.REJECTED,
            occurred_at=NOW,
            correlation_id="correlation-1",
            event_hash=HASH,
            retention_policy_id=uuid4(),
        )


def test_audit_event_carries_hash_chain_metadata() -> None:
    event = AuditEvent(
        audit_event_id=uuid4(),
        entity_type="PaymentRequest",
        entity_id="request-1",
        actor=actor(),
        action=AuditAction.APPROVED,
        occurred_at=NOW,
        correlation_id="correlation-1",
        previous_hash=HASH,
        event_hash="b" * 64,
        retention_policy_id=uuid4(),
    )

    assert event.previous_hash == HASH
    assert event.event_hash == "b" * 64
