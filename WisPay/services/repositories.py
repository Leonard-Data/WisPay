"""Durable store contracts for the approval workflow slice.

Protocols live here so services stay free of pyodbc (ADR-0005 seam): SQL
implementations are in ``sql_repositories`` and in-memory doubles used by
unit tests live in ``tests/services/fakes.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from WisPay.models import AuditEvent, PaymentRequest, WorkflowInstance
    from WisPay.services.workflow_rules import WorkflowRule


@runtime_checkable
class RequestStore(Protocol):
    """Persistence for :class:`PaymentRequest` aggregates."""

    def save(self, request: PaymentRequest) -> None:
        """Insert or update by ``request_id``; never deletes."""
        ...

    def get(self, request_id: UUID) -> PaymentRequest | None:
        """Return the stored aggregate or ``None``."""
        ...

    def get_by_number(self, request_number: str) -> PaymentRequest | None:
        """Return the aggregate with this immutable request number or ``None``."""
        ...


@runtime_checkable
class WorkflowStore(Protocol):
    """Persistence for frozen :class:`WorkflowInstance` route snapshots."""

    def save_instance(self, instance: WorkflowInstance) -> None:
        """Insert or update the instance (steps ride inside the payload)."""
        ...

    def get_instance(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        """Return the stored instance or ``None``."""
        ...

    def latest_instance_for_request(self, request_id: UUID) -> WorkflowInstance | None:
        """Return the newest instance generated for the request or ``None``."""
        ...

    def pending_instances(self) -> tuple[WorkflowInstance, ...]:
        """Return instances whose outcome is ``Pending``, newest first."""
        ...


@runtime_checkable
class AuditEventStore(Protocol):
    """Append-only persistence for hash-chained :class:`AuditEvent` records."""

    def last_event_hash(self) -> str:
        """Return the newest chain hash, or the genesis hash when empty."""
        ...

    def append(self, event: AuditEvent) -> None:
        """Persist one event; updates and deletes do not exist."""
        ...

    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        """Return the request's events oldest-first."""
        ...


@runtime_checkable
class RuleStore(Protocol):
    """Versioned approval-route configuration rows."""

    def active_version(self) -> str:
        """Return the currently activated workflow-rule version."""
        ...

    def rules(self, version: str) -> tuple[WorkflowRule, ...]:
        """Return the ordered rule rows recorded for ``version``."""
        ...


@dataclass(frozen=True, slots=True)
class Stores:
    """Bundle of store implementations handed to callers."""

    requests: RequestStore
    workflows: WorkflowStore
    audit: AuditEventStore
    rules: RuleStore
