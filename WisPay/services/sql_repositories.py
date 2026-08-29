"""SQL-backed implementations of the durable store contracts.

Every store takes an open :class:`pyodbc.Connection`; services never see the
driver. Timestamps are stored as UTC ISO-8601 strings (see ``db`` module
docstring). All queries are parameterized — no string interpolation of values.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from WisPay.models import (
    AuditEvent,
    AuditValueSnapshot,
    PaymentRecord,
    PaymentRequest,
    UserSnapshot,
    WorkflowInstance,
)
from WisPay.models.enums import AuditAction, RequestType, RoleName
from WisPay.services.audit_trail import (
    GENESIS_HASH,
    _event_payload,
    canonical_payload,
    chain_hash,
)
from WisPay.services.db import ensure_schema as _ensure_schema
from WisPay.services.repositories import AuditEventStore, Stores
from WisPay.services.workflow_rules import SEED_RULE_VERSION, WorkflowRule, seed_rules_v1

if TYPE_CHECKING:
    import pyodbc


def utc_iso(value: datetime) -> str:
    """Render an aware datetime as a UTC ISO-8601 string."""
    return value.astimezone(UTC).isoformat()


def parse_utc_iso(value: str) -> datetime:
    """Parse a stored UTC ISO-8601 string back into an aware datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _as_text(value: object) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _optional_text(row: tuple[object, ...], index: int) -> str | None:
    raw = row[index]
    return None if raw is None else _as_text(raw)


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #

_REQUEST_UPDATE = (
    "UPDATE dbo.wispay_payment_request "
    "SET request_number = ?, lifecycle_state = ?, payload = ?, updated_at_utc = ? "
    "WHERE request_id = ?"
)
_REQUEST_INSERT = (
    "INSERT INTO dbo.wispay_payment_request "
    "(request_id, request_number, lifecycle_state, payload, created_at_utc, updated_at_utc) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
_REQUEST_BY_ID = "SELECT payload FROM dbo.wispay_payment_request WHERE request_id = ?"
_REQUEST_BY_NUMBER = "SELECT payload FROM dbo.wispay_payment_request WHERE request_number = ?"
_REQUEST_LIST = "SELECT payload FROM dbo.wispay_payment_request ORDER BY created_at_utc ASC"


def request_insert_params(request: PaymentRequest) -> tuple[object, ...]:
    """Pure parameter builder for ``_REQUEST_INSERT`` (unit-tested without a DB)."""
    return (
        str(request.request_id),
        request.request_number,
        request.lifecycle_state.value,
        request.model_dump_json(),
        utc_iso(request.created_at),
        utc_iso(request.updated_at),
    )


class SqlRequestStore:
    """Upsert-only persistence for payment requests."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def save(self, request: PaymentRequest) -> None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                _REQUEST_UPDATE,
                request.request_number,
                request.lifecycle_state.value,
                request.model_dump_json(),
                utc_iso(request.updated_at),
                str(request.request_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(_REQUEST_INSERT, request_insert_params(request))
        finally:
            cursor.close()
        self._conn.commit()

    def get(self, request_id: UUID) -> PaymentRequest | None:
        return self._fetch_one(_REQUEST_BY_ID, str(request_id))

    def get_by_number(self, request_number: str) -> PaymentRequest | None:
        return self._fetch_one(_REQUEST_BY_NUMBER, request_number)

    def list_all(self) -> tuple[PaymentRequest, ...]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_REQUEST_LIST)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(PaymentRequest.model_validate_json(_as_text(row[0])) for row in rows)

    def _fetch_one(self, query: str, param: str) -> PaymentRequest | None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(query, param)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return PaymentRequest.model_validate_json(_as_text(row[0]))


# --------------------------------------------------------------------------- #
# Workflow instances
# --------------------------------------------------------------------------- #

_INSTANCE_UPDATE = (
    "UPDATE dbo.wispay_workflow_instance "
    "SET rule_version = ?, outcome = ?, current_step_sequence = ?, "
    "generated_at_utc = ?, payload = ? "
    "WHERE workflow_instance_id = ?"
)
_INSTANCE_INSERT = (
    "INSERT INTO dbo.wispay_workflow_instance "
    "(workflow_instance_id, request_id, rule_version, outcome, current_step_sequence, "
    "generated_at_utc, payload) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
_INSTANCE_BY_ID = "SELECT payload FROM dbo.wispay_workflow_instance WHERE workflow_instance_id = ?"
_INSTANCE_LATEST_FOR_REQUEST = (
    "SELECT payload FROM dbo.wispay_workflow_instance "
    "WHERE request_id = ? ORDER BY generated_at_utc DESC"
)
_INSTANCES_PENDING = (
    "SELECT payload FROM dbo.wispay_workflow_instance "
    "WHERE outcome = N'Pending' ORDER BY generated_at_utc DESC"
)


def instance_insert_params(instance: WorkflowInstance) -> tuple[object, ...]:
    """Pure parameter builder for ``_INSTANCE_INSERT`` (unit-tested without a DB)."""
    current_sequence = (
        None if instance.current_step_sequence is None else instance.current_step_sequence
    )
    return (
        str(instance.workflow_instance_id),
        str(instance.request_id),
        instance.workflow_rule_version,
        instance.final_outcome.value,
        current_sequence,
        utc_iso(instance.generated_at),
        instance.model_dump_json(),
    )


class SqlWorkflowStore:
    """Upsert-only persistence for frozen workflow route snapshots."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def save_instance(self, instance: WorkflowInstance) -> None:
        current_sequence = (
            None if instance.current_step_sequence is None else instance.current_step_sequence
        )
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                _INSTANCE_UPDATE,
                instance.workflow_rule_version,
                instance.final_outcome.value,
                current_sequence,
                utc_iso(instance.generated_at),
                instance.model_dump_json(),
                str(instance.workflow_instance_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(_INSTANCE_INSERT, instance_insert_params(instance))
        finally:
            cursor.close()
        self._conn.commit()

    def get_instance(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        return self._fetch_one(_INSTANCE_BY_ID, str(workflow_instance_id))

    def latest_instance_for_request(self, request_id: UUID) -> WorkflowInstance | None:
        return self._fetch_one(_INSTANCE_LATEST_FOR_REQUEST, str(request_id))

    def pending_instances(self) -> tuple[WorkflowInstance, ...]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_INSTANCES_PENDING)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(WorkflowInstance.model_validate_json(_as_text(row[0])) for row in rows)

    def _fetch_one(self, query: str, param: str) -> WorkflowInstance | None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(query, param)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return WorkflowInstance.model_validate_json(_as_text(row[0]))


# --------------------------------------------------------------------------- #
# Audit events
# --------------------------------------------------------------------------- #

_AUDIT_INSERT = (
    "INSERT INTO dbo.wispay_audit_event "
    "(audit_event_id, entity_type, entity_id, actor_external_identity_id, action, "
    "occurred_at_utc, reason, new_value, correlation_id, previous_hash, event_hash, "
    "retention_policy_id, recorded_at_utc, payload) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_AUDIT_LAST_HASH = "SELECT TOP 1 event_hash FROM dbo.wispay_audit_event ORDER BY sequence DESC"
_AUDIT_FOR_CORRELATION = (
    "SELECT payload FROM dbo.wispay_audit_event WHERE correlation_id = ? ORDER BY sequence ASC"
)


def audit_insert_params(event: AuditEvent, *, recorded_at_utc: str) -> tuple[object, ...]:
    """Pure parameter builder for ``_AUDIT_INSERT`` (unit-tested without a DB)."""
    return (
        str(event.audit_event_id),
        event.entity_type,
        event.entity_id,
        event.actor.external_identity_id,
        event.action.value,
        utc_iso(event.occurred_at),
        event.reason,
        None if event.new_value is None else event.new_value.canonical_json,
        event.correlation_id,
        event.previous_hash,
        event.event_hash,
        str(event.retention_policy_id),
        recorded_at_utc,
        event.model_dump_json(),
    )


class SqlAuditEventStore:
    """Append-only audit persistence; reads rebuild full model payloads."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def last_event_hash(self) -> str:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_AUDIT_LAST_HASH)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return GENESIS_HASH if row is None else _as_text(row[0])

    def append(self, event: AuditEvent) -> None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                _AUDIT_INSERT, audit_insert_params(event, recorded_at_utc=utc_iso(_now()))
            )
        finally:
            cursor.close()
        self._conn.commit()

    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_AUDIT_FOR_CORRELATION, correlation_id)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(AuditEvent.model_validate_json(_as_text(row[0])) for row in rows)


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Workflow rules
# --------------------------------------------------------------------------- #

_RULE_SELECT = (
    "SELECT version, priority, request_type, min_amount, currency_code, "
    "legal_entity_code, department_code, project_code, risk_flag, step_sequence, "
    "parallel_group, approver_role, approver_external_identity_id, "
    "approver_display_name, approver_email, approver_captured_at_utc, due_days "
    "FROM dbo.wispay_workflow_rule "
    "WHERE version = ? AND is_active = 1 "
    "ORDER BY priority ASC, step_sequence ASC"
)
_RULE_INSERT = (
    "INSERT INTO dbo.wispay_workflow_rule "
    "(version, priority, request_type, min_amount, currency_code, legal_entity_code, "
    "department_code, project_code, risk_flag, step_sequence, parallel_group, "
    "approver_role, approver_external_identity_id, approver_display_name, "
    "approver_email, approver_captured_at_utc, due_days, is_active) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)"
)
_RULE_VERSION_EXISTS = (
    "SELECT TOP 1 version FROM dbo.wispay_workflow_rule_version WHERE version = ?"
)
_RULE_VERSION_INSERT = (
    "INSERT INTO dbo.wispay_workflow_rule_version (version, activated_at_utc) VALUES (?, ?)"
)
_ACTIVE_VERSION = (
    "SELECT TOP 1 version FROM dbo.wispay_workflow_rule_version ORDER BY activated_at_utc DESC"
)

_RULE_COLUMNS = 17


class SqlRuleStore:
    """Versioned approval-route configuration rows with idempotent seeding."""

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def active_version(self) -> str:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_ACTIVE_VERSION)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            raise RuntimeError("No workflow rule version has been seeded.")
        return _as_text(row[0])

    def rules(self, version: str) -> tuple[WorkflowRule, ...]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_RULE_SELECT, version)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(_rule_from_row(row) for row in rows)

    def ensure_seeded(self, version: str = SEED_RULE_VERSION) -> None:
        """Insert the seed rule set once; later calls are no-ops."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(_RULE_VERSION_EXISTS, version)
            if cursor.fetchone() is not None:
                return
            for rule in seed_rules_v1():
                cursor.execute(_RULE_INSERT, rule_insert_params(rule))
            cursor.execute(_RULE_VERSION_INSERT, version, utc_iso(_now()))
        finally:
            cursor.close()
        self._conn.commit()


def rule_insert_params(rule: WorkflowRule) -> tuple[object, ...]:
    """Pure parameter builder for ``_RULE_INSERT`` (unit-tested without a DB)."""
    min_amount = None if rule.min_amount is None else str(rule.min_amount)
    return (
        rule.version,
        rule.priority,
        None if rule.request_type is None else rule.request_type.value,
        min_amount,
        rule.currency_code,
        rule.legal_entity_code,
        rule.department_code,
        rule.project_code,
        rule.risk_flag,
        rule.step_sequence,
        rule.parallel_group,
        rule.approver_role.value,
        rule.approver_user.external_identity_id,
        rule.approver_user.display_name,
        rule.approver_user.email,
        utc_iso(rule.approver_user.captured_at),
        rule.due_days,
    )


def _rule_from_row(row: tuple[object, ...]) -> WorkflowRule:
    if len(row) < _RULE_COLUMNS:
        raise RuntimeError(f"workflow rule row has {len(row)} columns, expected {_RULE_COLUMNS}")
    min_amount_raw = _optional_text(row, 3)
    request_type_raw = _optional_text(row, 2)
    return WorkflowRule(
        version=_as_text(row[0]),
        priority=int(str(row[1])),
        request_type=None if request_type_raw is None else RequestType(request_type_raw),
        min_amount=None if min_amount_raw is None else Decimal(min_amount_raw),
        currency_code=_optional_text(row, 4),
        legal_entity_code=_optional_text(row, 5),
        department_code=_optional_text(row, 6),
        project_code=_optional_text(row, 7),
        risk_flag=_optional_text(row, 8),
        step_sequence=int(str(row[9])),
        parallel_group=_optional_text(row, 10),
        approver_role=RoleName(_as_text(row[11])),
        approver_user=UserSnapshot(
            external_identity_id=_as_text(row[12]),
            display_name=_as_text(row[13]),
            email=_as_text(row[14]),
            captured_at=parse_utc_iso(_as_text(row[15])),
        ),
        due_days=None if row[16] is None else int(str(row[16])),
    )


# --------------------------------------------------------------------------- #
# Durable audit trail
# --------------------------------------------------------------------------- #


class DurableAuditTrail:
    """Hash-chained audit trail persisted through an ``AuditEventStore``.

    Chain math is shared with the session trail (``audit_trail``): each event's
    ``previous_hash`` comes from ``store.last_event_hash()`` so links survive
    process restarts. The chain spans all correlations in insert order;
    per-request reads preserve relative order via the sequence column.
    """

    def __init__(
        self,
        store: AuditEventStore,
        *,
        retention_policy_id: UUID,
    ) -> None:
        self._store = store
        self._retention_policy_id = retention_policy_id

    def append(
        self,
        *,
        entity_type: str,
        entity_id: str,
        actor: UserSnapshot,
        action: AuditAction,
        occurred_at: datetime,
        new_value: str | None = None,
        reason: str | None = None,
        correlation_id: str,
        retention_policy_id: UUID | None = None,
    ) -> AuditEvent:
        """Construct, chain, and persist one audit event."""
        policy_id = (
            self._retention_policy_id if retention_policy_id is None else retention_policy_id
        )
        previous_hash = self._store.last_event_hash()
        payload_json = canonical_payload(
            _event_payload(
                entity_type=entity_type,
                entity_id=entity_id,
                actor=actor,
                action=action,
                occurred_at=occurred_at,
                new_value=new_value,
                correlation_id=correlation_id,
                retention_policy_id=policy_id,
                previous_hash=previous_hash,
            )
        )
        event = AuditEvent(
            audit_event_id=uuid4(),
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            action=action,
            occurred_at=occurred_at,
            new_value=(None if new_value is None else AuditValueSnapshot(canonical_json=new_value)),
            reason=reason,
            correlation_id=correlation_id,
            previous_hash=previous_hash,
            event_hash=chain_hash(previous_hash, payload_json),
            retention_policy_id=policy_id,
        )
        self._store.append(event)
        return event

    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        """Return the persisted events for one request, oldest first."""
        return self._store.events_for_request(correlation_id)


# --------------------------------------------------------------------------- #
# Payment records
# --------------------------------------------------------------------------- #


_PAYMENT_RECORD_INSERT = (
    "INSERT INTO dbo.wispay_payment_record "
    "(payment_record_id, request_id, recorded_at_utc, payload) "
    "VALUES (?, ?, ?, ?)"
)
_PAYMENT_RECORD_FOR_REQUEST = (
    "SELECT payload FROM dbo.wispay_payment_record "
    "WHERE request_id = ? ORDER BY recorded_at_utc ASC"
)


def payment_record_insert_params(record: PaymentRecord) -> tuple[object, ...]:
    """Pure parameter builder for ``_PAYMENT_RECORD_INSERT``."""
    return (
        str(record.payment_record_id),
        str(record.request_id),
        utc_iso(record.recorded_at),
        record.model_dump_json(),
    )


class SqlPaymentRecordStore:
    """Append-only payment-record persistence (Azure SQL).

    CONTEXT.md invariant 10: no hard-deletes. The store exposes ``save``
    (insert) plus ``for_request`` (read) only. The ``payment_record_id`` PK
    guarantees idempotent inserts on retry; duplicate-key collisions surface
    to callers so the upstream service can fail loudly rather than silently
    overwrite a recorded payment.
    """

    def __init__(self, conn: pyodbc.Connection) -> None:
        self._conn = conn

    def save(self, record: PaymentRecord) -> None:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_PAYMENT_RECORD_INSERT, payment_record_insert_params(record))
        finally:
            cursor.close()
        self._conn.commit()

    def for_request(self, request_id: UUID) -> tuple[PaymentRecord, ...]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(_PAYMENT_RECORD_FOR_REQUEST, str(request_id))
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(PaymentRecord.model_validate_json(_as_text(row[0])) for row in rows)


# --------------------------------------------------------------------------- #
# Bundle
# --------------------------------------------------------------------------- #


def sql_stores(conn: pyodbc.Connection, *, ensure_tables: bool = True) -> Stores:
    """Build stores bound to ``conn``, bootstrap schema, and seed rules v1."""
    if ensure_tables:
        _ensure_schema(conn)
    rules = SqlRuleStore(conn)
    rules.ensure_seeded()
    return Stores(
        requests=SqlRequestStore(conn),
        workflows=SqlWorkflowStore(conn),
        audit=SqlAuditEventStore(conn),
        payments=SqlPaymentRecordStore(conn),
        rules=rules,
    )
