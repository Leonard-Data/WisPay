-- WisPay durable schema — SQLite variant (mirrors WisPay/services/sqlite_repositories.py::_SQLITE_SCHEMA_STATEMENTS).
-- Used by dev / CI installs (BE-1): the same canonical logical records are stored
-- without an ODBC driver. See docs/reference/backend/data-model.md and ADR-0004.
--
-- Timestamps are UTC ISO-8601 strings; JSON payload columns are the source of
-- truth for canonical model shapes. Rule seeding lives in code:
-- WisPay/services/workflow_rules.py::seed_rules_v1 via SqliteRuleStore.ensure_seeded.
-- Every statement is individually idempotent; re-running this file is safe.

CREATE TABLE IF NOT EXISTS wispay_payment_request (
    request_id TEXT NOT NULL PRIMARY KEY,
    request_number TEXT NULL,
    lifecycle_state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS UX_wispay_payment_request_number
    ON wispay_payment_request (request_number)
    WHERE request_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS wispay_workflow_instance (
    workflow_instance_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    outcome TEXT NOT NULL,
    current_step_sequence INTEGER NULL,
    generated_at_utc TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_wispay_workflow_instance_request
    ON wispay_workflow_instance (request_id, generated_at_utc);

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
);

CREATE TABLE IF NOT EXISTS wispay_workflow_rule_version (
    version TEXT NOT NULL PRIMARY KEY,
    activated_at_utc TEXT NOT NULL
);

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
);

CREATE INDEX IF NOT EXISTS IX_wispay_audit_event_correlation
    ON wispay_audit_event (correlation_id, sequence);

CREATE TABLE IF NOT EXISTS wispay_payment_record (
    payment_record_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL,
    recorded_at_utc TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_wispay_payment_record_request
    ON wispay_payment_record (request_id, recorded_at_utc);
