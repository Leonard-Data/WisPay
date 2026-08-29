"""SQLite-backed implementations of the durable store contracts.

This module mirrors :mod:`WisPay.services.sql_repositories` shape-for-shape
against the same :class:`Stores` Protocol. Every service in the app talks to
the Protocol only, so swapping drivers is a one-line change in
:mod:`WisPay.services.runtime` (or :mod:`WisPay.services.db.stores`).

Design notes
------------

- Connection-per-process. SQLite's :func:`sqlite3.connect` already serializes
  writes; WAL mode is enabled in :mod:`WisPay.services.db.sqlite_connect` for
  better read concurrency.
- UUIDs are stored as ``TEXT`` in canonical 8-4-4-4-12 form so values round
  trip through :func:`str(UUID)` and :class:`uuid.UUID` without precision
  loss.
- ``payload`` columns are the source of truth for canonical model shapes
  (mirrors the Azure SQL implementation); the indexed ``request_number`` /
  ``correlation_id`` / ``(request_id, generated_at)`` columns only accelerate
  lookups.
- All money fields pass through ``WisPay.models.Money`` validation; the
  schema stores them as ``TEXT`` (canonical JSON) inside the model payload
  so the canonical ``Decimal`` (with ``decimal_scale``) is preserved without
  any float coercion.
- No ``DELETE`` is exposed for financial or audit tables (ADR-0004 cross-
  cutting rule 4 + CONTEXT.md invariant 10).
"""

from __future__ import annotations

# ``sqlite3`` is used at runtime by ``isinstance`` checks below, so it cannot
# move into a ``TYPE_CHECKING`` block.
import sqlite3  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from WisPay.models import (
    AuditEvent,
    PaymentRecord,
    PaymentRequest,
    WorkflowInstance,
)
from WisPay.services.audit_trail import GENESIS_HASH
from WisPay.services.db import sqlite_connect
from WisPay.services.repositories import Stores
from WisPay.services.sql_repositories import (
    _rule_from_row,
    audit_insert_params,
    instance_insert_params,
    request_insert_params,
    rule_insert_params,
    utc_iso,
)
from WisPay.services.workflow_rules import SEED_RULE_VERSION, seed_rules_v1

if TYPE_CHECKING:
    from uuid import UUID

    from WisPay.services.workflow_rules import WorkflowRule

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

# Mirrors scripts/sql/schema.sqlite.sql. ``CREATE TABLE IF NOT EXISTS`` is
# idempotent; indexes use the same name. Same five tables as the Azure SQL
# path; column types widened to SQLite-friendly primitives (UNIQUEIDENTIFIER
# → TEXT, DECIMAL/NVARCHAR/BIT → TEXT/INTEGER), and surrogate ``sequence`` /
# ``rule_id`` columns are auto-incremented by SQLite.
_SQLITE_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS wispay_payment_request (
        request_id TEXT NOT NULL PRIMARY KEY,
        request_number TEXT NULL,
        lifecycle_state TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS UX_wispay_payment_request_number
        ON wispay_payment_request (request_number)
        WHERE request_number IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS wispay_workflow_instance (
        workflow_instance_id TEXT NOT NULL PRIMARY KEY,
        request_id TEXT NOT NULL,
        rule_version TEXT NOT NULL,
        outcome TEXT NOT NULL,
        current_step_sequence INTEGER NULL,
        generated_at_utc TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS IX_wispay_workflow_instance_request
        ON wispay_workflow_instance (request_id, generated_at_utc)
    """,
    """
    CREATE TABLE IF NOT EXISTS wispay_workflow_rule (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL,
        priority INTEGER NOT NULL,
        request_type TEXT NULL,
        min_amount TEXT NULL,
        currency_code TEXT NULL,
        legal_entity_code TEXT NULL,
        department_code TEXT NULL,
        project_code TEXT NULL,
        risk_flag TEXT NULL,
        step_sequence INTEGER NOT NULL,
        parallel_group TEXT NULL,
        approver_role TEXT NOT NULL,
        approver_external_identity_id TEXT NOT NULL,
        approver_display_name TEXT NOT NULL,
        approver_email TEXT NOT NULL,
        approver_captured_at_utc TEXT NOT NULL,
        due_days INTEGER NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        UNIQUE (version, priority, step_sequence, approver_external_identity_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wispay_workflow_rule_version (
        version TEXT NOT NULL PRIMARY KEY,
        activated_at_utc TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wispay_audit_event (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_event_id TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        actor_external_identity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        occurred_at_utc TEXT NOT NULL,
        reason TEXT NULL,
        new_value TEXT NULL,
        correlation_id TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL,
        retention_policy_id TEXT NOT NULL,
        recorded_at_utc TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS IX_wispay_audit_event_correlation
        ON wispay_audit_event (correlation_id, sequence)
    """,
    """
    CREATE TABLE IF NOT EXISTS wispay_payment_record (
        payment_record_id TEXT NOT NULL PRIMARY KEY,
        request_id TEXT NOT NULL,
        recorded_at_utc TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS IX_wispay_payment_record_request
        ON wispay_payment_record (request_id, recorded_at_utc)
    """,
)


def sqlite_schema_statements() -> tuple[str, ...]:
    """Expose the managed SQLite DDL statements (used by tests and tooling)."""
    return _SQLITE_SCHEMA_STATEMENTS


def ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Create any missing ``wispay_*`` tables and indexes. Idempotent."""
    for statement in _SQLITE_SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _now() -> datetime:
    return datetime.now(UTC)


def _row_payload(row: tuple[Any, ...] | None) -> str | None:
    if row is None:
        return None
    return str(row[0])


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


class SqliteRequestStore:
    """Upsert-only persistence for payment requests (SQLite)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, request: PaymentRequest) -> None:
        params = request_insert_params(request)
        with self._conn:
            # ``INSERT ... ON CONFLICT DO UPDATE`` keeps the upsert atomic
            # without depending on ``changes()`` (which returns 0 when the
            # UPDATE matches but writes identical values, leading to a phantom
            # unique-constraint failure on the follow-up INSERT).
            self._conn.execute(
                """
                INSERT INTO wispay_payment_request
                (request_id, request_number, lifecycle_state, payload, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    request_number = excluded.request_number,
                    lifecycle_state = excluded.lifecycle_state,
                    payload = excluded.payload,
                    updated_at_utc = excluded.updated_at_utc
                """,
                params,
            )

    def get(self, request_id: UUID) -> PaymentRequest | None:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_payment_request WHERE request_id = ?",
            (str(request_id),),
        )
        row = cursor.fetchone()
        return None if row is None else PaymentRequest.model_validate_json(str(row[0]))

    def get_by_number(self, request_number: str) -> PaymentRequest | None:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_payment_request WHERE request_number = ?",
            (request_number,),
        )
        row = cursor.fetchone()
        return None if row is None else PaymentRequest.model_validate_json(str(row[0]))

    def list_all(self) -> tuple[PaymentRequest, ...]:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_payment_request ORDER BY created_at_utc ASC"
        )
        return tuple(PaymentRequest.model_validate_json(str(row[0])) for row in cursor.fetchall())


# --------------------------------------------------------------------------- #
# Workflow instances
# --------------------------------------------------------------------------- #


class SqliteWorkflowStore:
    """Upsert-only persistence for frozen workflow route snapshots (SQLite)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_instance(self, instance: WorkflowInstance) -> None:
        params = instance_insert_params(instance)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO wispay_workflow_instance
                (workflow_instance_id, request_id, rule_version, outcome,
                 current_step_sequence, generated_at_utc, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_instance_id) DO UPDATE SET
                    rule_version = excluded.rule_version,
                    outcome = excluded.outcome,
                    current_step_sequence = excluded.current_step_sequence,
                    generated_at_utc = excluded.generated_at_utc,
                    payload = excluded.payload
                """,
                params,
            )

    def get_instance(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_workflow_instance WHERE workflow_instance_id = ?",
            (str(workflow_instance_id),),
        )
        row = cursor.fetchone()
        return None if row is None else WorkflowInstance.model_validate_json(str(row[0]))

    def latest_instance_for_request(self, request_id: UUID) -> WorkflowInstance | None:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_workflow_instance "
            "WHERE request_id = ? ORDER BY generated_at_utc DESC",
            (str(request_id),),
        )
        row = cursor.fetchone()
        return None if row is None else WorkflowInstance.model_validate_json(str(row[0]))

    def pending_instances(self) -> tuple[WorkflowInstance, ...]:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_workflow_instance "
            "WHERE outcome = 'Pending' ORDER BY generated_at_utc DESC"
        )
        return tuple(WorkflowInstance.model_validate_json(str(row[0])) for row in cursor.fetchall())


# --------------------------------------------------------------------------- #
# Audit events
# --------------------------------------------------------------------------- #


class SqliteAuditEventStore:
    """Append-only audit persistence (SQLite). Reads rebuild full model payloads."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def last_event_hash(self) -> str:
        cursor = self._conn.execute(
            "SELECT event_hash FROM wispay_audit_event ORDER BY sequence DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return GENESIS_HASH if row is None else str(row[0])

    def append(self, event: AuditEvent) -> None:
        params = audit_insert_params(event, recorded_at_utc=utc_iso(_now()))
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO wispay_audit_event
                (audit_event_id, entity_type, entity_id, actor_external_identity_id, action,
                 occurred_at_utc, reason, new_value, correlation_id, previous_hash, event_hash,
                 retention_policy_id, recorded_at_utc, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )

    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_audit_event WHERE correlation_id = ? ORDER BY sequence ASC",
            (correlation_id,),
        )
        return tuple(AuditEvent.model_validate_json(str(row[0])) for row in cursor.fetchall())


# --------------------------------------------------------------------------- #
# Workflow rules
# --------------------------------------------------------------------------- #


_RULE_COLUMNS_SQLITE = (
    "version, priority, request_type, min_amount, currency_code, "
    "legal_entity_code, department_code, project_code, risk_flag, step_sequence, "
    "parallel_group, approver_role, approver_external_identity_id, "
    "approver_display_name, approver_email, approver_captured_at_utc, due_days"
)


class SqliteRuleStore:
    """Versioned approval-route configuration rows with idempotent seeding (SQLite)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def active_version(self) -> str:
        cursor = self._conn.execute(
            "SELECT version FROM wispay_workflow_rule_version ORDER BY activated_at_utc DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("No workflow rule version has been seeded.")
        return str(row[0])

    def rules(self, version: str) -> tuple[WorkflowRule, ...]:
        cursor = self._conn.execute(
            f"SELECT {_RULE_COLUMNS_SQLITE} FROM wispay_workflow_rule "
            "WHERE version = ? AND is_active = 1 "
            "ORDER BY priority ASC, step_sequence ASC",
            (version,),
        )
        return tuple(_rule_from_row(tuple(row)) for row in cursor.fetchall())

    def ensure_seeded(self, version: str = SEED_RULE_VERSION) -> None:
        cursor = self._conn.execute(
            "SELECT 1 FROM wispay_workflow_rule_version WHERE version = ?", (version,)
        )
        if cursor.fetchone() is not None:
            return
        with self._conn:
            for rule in seed_rules_v1():
                self._conn.execute(
                    f"""
                    INSERT INTO wispay_workflow_rule
                    ({_RULE_COLUMNS_SQLITE}, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    rule_insert_params(rule),
                )
            self._conn.execute(
                "INSERT INTO wispay_workflow_rule_version (version, activated_at_utc) "
                "VALUES (?, ?)",
                (version, utc_iso(_now())),
            )


# --------------------------------------------------------------------------- #
# Payment records
# --------------------------------------------------------------------------- #


class SqlitePaymentRecordStore:
    """Append-only payment-record persistence (SQLite).

    Mirrors :class:`SqlPaymentRecordStore` against the dev driver. CONTEXT.md
    invariant 10 forbids hard-deletes; this store exposes ``save`` (insert)
    plus ``for_request`` (read) only.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, record: PaymentRecord) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO wispay_payment_record
                (payment_record_id, request_id, recorded_at_utc, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(payment_record_id) DO NOTHING
                """,
                (
                    str(record.payment_record_id),
                    str(record.request_id),
                    utc_iso(record.recorded_at),
                    record.model_dump_json(),
                ),
            )

    def for_request(self, request_id: UUID) -> tuple[PaymentRecord, ...]:
        cursor = self._conn.execute(
            "SELECT payload FROM wispay_payment_record "
            "WHERE request_id = ? ORDER BY recorded_at_utc ASC",
            (str(request_id),),
        )
        return tuple(PaymentRecord.model_validate_json(str(row[0])) for row in cursor.fetchall())


# --------------------------------------------------------------------------- #
# Bundle
# --------------------------------------------------------------------------- #


def sqlite_stores(
    *,
    conn: sqlite3.Connection | None = None,
    ensure_tables: bool = True,
) -> Stores:
    """Build SQLite-backed stores; bootstrap schema and seed rules v1.

    When ``conn`` is ``None`` a fresh connection is opened from the active
    ``WS_DB_URL`` (so dev / CI invocations match production boot semantics).
    """
    if conn is None:
        conn = sqlite_connect()
    if ensure_tables:
        ensure_sqlite_schema(conn)
    rules = SqliteRuleStore(conn)
    rules.ensure_seeded()
    return Stores(
        requests=SqliteRequestStore(conn),
        workflows=SqliteWorkflowStore(conn),
        audit=SqliteAuditEventStore(conn),
        payments=SqlitePaymentRecordStore(conn),
        rules=rules,
    )
