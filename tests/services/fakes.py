"""In-memory doubles of the durable store contracts for unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from WisPay.services.audit_trail import GENESIS_HASH
from WisPay.services.repositories import Stores
from WisPay.services.sql_repositories import DurableAuditTrail
from WisPay.services.workflow_rules import SEED_RULE_VERSION, WorkflowRule

if TYPE_CHECKING:
    from WisPay.models import (
        AuditEvent,
        PaymentRecord,
        PaymentRequest,
        WorkflowInstance,
    )


class FakeRequestStore:
    """Dictionary-backed request persistence."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, PaymentRequest] = {}

    def save(self, request: PaymentRequest) -> None:
        self._by_id[request.request_id] = request

    def get(self, request_id: UUID) -> PaymentRequest | None:
        return self._by_id.get(request_id)

    def get_by_number(self, request_number: str) -> PaymentRequest | None:
        return next(
            (
                request
                for request in self._by_id.values()
                if request.request_number == request_number
            ),
            None,
        )

    def list_all(self) -> tuple[PaymentRequest, ...]:
        return tuple(sorted(self._by_id.values(), key=lambda req: req.created_at))

    def count(self) -> int:
        return len(self._by_id)


class FakeWorkflowStore:
    """Dictionary-backed workflow-instance persistence."""

    def __init__(self) -> None:
        self._instances: dict[UUID, WorkflowInstance] = {}

    def save_instance(self, instance: WorkflowInstance) -> None:
        self._instances[instance.workflow_instance_id] = instance

    def get_instance(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        return self._instances.get(workflow_instance_id)

    def latest_instance_for_request(self, request_id: UUID) -> WorkflowInstance | None:
        matching = [
            instance for instance in self._instances.values() if instance.request_id == request_id
        ]
        if not matching:
            return None
        return max(matching, key=lambda instance: instance.generated_at)

    def pending_instances(self) -> tuple[WorkflowInstance, ...]:
        pending = [
            instance
            for instance in self._instances.values()
            if instance.final_outcome.value == "Pending"
        ]
        return tuple(sorted(pending, key=lambda i: i.generated_at, reverse=True))


class FakeAuditEventStore:
    """List-backed append-only audit persistence."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def last_event_hash(self) -> str:
        return self._events[-1].event_hash if self._events else GENESIS_HASH

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        return tuple(event for event in self._events if event.correlation_id == correlation_id)


class FakeRuleStore:
    """Configurable single-version rule source."""

    def __init__(
        self,
        *,
        version: str = SEED_RULE_VERSION,
        rules: tuple[WorkflowRule, ...] = (),
    ) -> None:
        self._version = version
        self._rules_by_version: dict[str, tuple[WorkflowRule, ...]] = {
            version: rules,
        }

    def active_version(self) -> str:
        return self._version

    def rules(self, version: str) -> tuple[WorkflowRule, ...]:
        return self._rules_by_version.get(version, ())

    def publish_version(self, version: str, rules: tuple[WorkflowRule, ...]) -> None:
        self._rules_by_version[version] = rules


class FakePaymentRecordStore:
    """Dictionary-backed append-only payment-record persistence."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, PaymentRecord] = {}

    def save(self, record: PaymentRecord) -> None:
        # Insert-only; updates are not exposed (CONTEXT.md invariant 10).
        self._by_id[record.payment_record_id] = record

    def for_request(self, request_id: UUID) -> tuple[PaymentRecord, ...]:
        records = [r for r in self._by_id.values() if r.request_id == request_id]
        records.sort(key=lambda record: record.recorded_at)
        return tuple(records)


class FakeStores:
    """Bundle mirroring :class:`Stores` with directly accessible doubles."""

    def __init__(
        self,
        *,
        rule_version: str = SEED_RULE_VERSION,
        rules: tuple[WorkflowRule, ...] = (),
    ) -> None:
        self.requests = FakeRequestStore()
        self.workflows = FakeWorkflowStore()
        self.audit = FakeAuditEventStore()
        self.payments = FakePaymentRecordStore()
        self.rules = FakeRuleStore(version=rule_version, rules=rules)

    @property
    def stores(self) -> Stores:
        return Stores(
            requests=self.requests,
            workflows=self.workflows,
            audit=self.audit,
            payments=self.payments,
            rules=self.rules,
        )


_TRAIL_RETENTION_POLICY_ID = UUID("00000000-0000-4000-8000-0000000000a1")


def durable_trail(store: FakeAuditEventStore | None = None) -> DurableAuditTrail:
    """Return a hash-chaining appender backed by an in-memory store."""
    return DurableAuditTrail(
        store if store is not None else FakeAuditEventStore(),
        retention_policy_id=_TRAIL_RETENTION_POLICY_ID,
    )
