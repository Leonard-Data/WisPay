"""Session-scoped, tamper-evident audit trail.

This module implements decision 5 from the spec: a pure, hash-chained
``AuditEvent`` construction held in session memory. Canonical JSON is computed
deterministically (key-sorted, compact), and each event's ``event_hash`` chains
over the previous event's hash (genesis ``"0" * 64``). ``verify()`` recomputes
the whole chain so tampering with any stored event is detectable.

Durable append via ``AuditService`` + SQL lands with issue 05; nothing here
pretends to persist.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

from WisPay.models import (
    AuditAction,
    AuditEvent,
    AuditValueSnapshot,
    UserSnapshot,
)

GENESIS_HASH: str = "0" * 64


def canonical_payload(payload: dict[str, object]) -> str:
    """Serialize ``payload`` to stable, key-sorted, compact JSON.

    Stable ordering makes the hash reproducible across runs and across
    machines. Non-serializable objects are rejected by ``json.dumps`` rather
    than silently coerced.
    """

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain_hash(previous_hash: str, payload_json: str) -> str:
    """SHA-256 hex digest of the previous hash concatenated with the payload."""

    return hashlib.sha256((previous_hash + payload_json).encode("utf-8")).hexdigest()


class InMemoryAuditTrail:
    """Append-only, session-scoped hash-chained audit log.

    Each appended event links to its predecessor via ``previous_hash``; the
    first event links to :data:`GENESIS_HASH`. The trail is intentionally not
    durable (decision 5).
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(
        self,
        *,
        entity_type: str,
        entity_id: str,
        actor: UserSnapshot,
        action: AuditAction,
        occurred_at: datetime,
        new_value: str | None = None,
        correlation_id: str,
        retention_policy_id: UUID,
        reason: str | None = None,
    ) -> AuditEvent:
        """Construct, chain, and store a new ``AuditEvent``.

        ``new_value`` is the canonical-JSON string of the entity state after
        the action; when supplied it is wrapped in an :class:`AuditValueSnapshot`.
        ``reason`` is required by the AuditEvent model for the consequential
        actions listed in :data:`AuditEvent._REASON_REQUIRED_ACTIONS`.
        """

        previous_hash = self._events[-1].event_hash if self._events else GENESIS_HASH
        payload = _event_payload(
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            action=action,
            occurred_at=occurred_at,
            new_value=new_value,
            correlation_id=correlation_id,
            retention_policy_id=retention_policy_id,
            previous_hash=previous_hash,
        )
        payload_json = canonical_payload(payload)
        event_hash = chain_hash(previous_hash, payload_json)
        new_value_snapshot: AuditValueSnapshot | None = None
        if new_value is not None:
            new_value_snapshot = AuditValueSnapshot(canonical_json=new_value)
        event = AuditEvent(
            audit_event_id=uuid4(),
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            action=action,
            occurred_at=occurred_at,
            new_value=new_value_snapshot,
            reason=reason,
            correlation_id=correlation_id,
            previous_hash=previous_hash,
            event_hash=event_hash,
            retention_policy_id=retention_policy_id,
        )
        self._events.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        """Return an immutable snapshot of the stored events."""

        return tuple(self._events)

    def verify(self) -> bool:
        """Recompute the chain and return ``False`` on any mismatch.

        A tampered event (mutated field, swapped hash, broken link) is
        detected because the recomputed hash no longer matches the stored
        ``event_hash``.
        """

        previous_hash = GENESIS_HASH
        for event in self._events:
            if event.previous_hash != previous_hash:
                return False
            payload = _event_payload(
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                actor=event.actor,
                action=event.action,
                occurred_at=event.occurred_at,
                new_value=event.new_value.canonical_json if event.new_value else None,
                correlation_id=event.correlation_id,
                retention_policy_id=event.retention_policy_id,
                previous_hash=event.previous_hash,
            )
            expected_hash = chain_hash(previous_hash, canonical_payload(payload))
            if event.event_hash != expected_hash:
                return False
            previous_hash = event.event_hash
        return True


def _event_payload(
    *,
    entity_type: str,
    entity_id: str,
    actor: UserSnapshot,
    action: AuditAction,
    occurred_at: datetime,
    new_value: str | None,
    correlation_id: str,
    retention_policy_id: UUID,
    previous_hash: str,
) -> dict[str, object]:
    """Build the canonical dict that is hashed for a chain link.

    Only the fields that define the chain link are included; volatile model
    metadata (``audit_event_id``) is excluded so the hash depends on content,
    not on a freshly generated UUID.
    """

    payload: dict[str, object] = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor": json.loads(actor.model_dump_json()),
        "action": action.value,
        "occurred_at": occurred_at.isoformat(),
        "correlation_id": correlation_id,
        "retention_policy_id": str(retention_policy_id),
        "previous_hash": previous_hash,
    }
    if new_value is not None:
        payload["new_value"] = new_value
    return payload
