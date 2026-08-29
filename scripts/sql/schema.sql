-- WisPay durable schema (mirrors WisPay/services/db.py::_SCHEMA_STATEMENTS).
-- Physical design maps canonical logical records (docs/reference/backend/data-model.md)
-- onto dbo.wispay_* tables. Timestamps are UTC ISO-8601 strings; JSON payload
-- columns are the source of truth. Rule seeding lives in code:
-- WisPay/services/workflow_rules.py::seed_rules_v1 via SqlRuleStore.ensure_seeded.
-- Every statement is individually idempotent; re-running this file is safe.

IF OBJECT_ID(N'dbo.wispay_payment_request', N'U') IS NULL
CREATE TABLE dbo.wispay_payment_request (
    request_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT PK_wispay_payment_request PRIMARY KEY,
    request_number NVARCHAR(32) NULL,
    lifecycle_state NVARCHAR(40) NOT NULL,
    payload NVARCHAR(MAX) NOT NULL,
    created_at_utc VARCHAR(35) NOT NULL,
    updated_at_utc VARCHAR(35) NOT NULL
);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_wispay_payment_request_number'
      AND object_id = OBJECT_ID(N'dbo.wispay_payment_request')
)
CREATE UNIQUE INDEX UX_wispay_payment_request_number
    ON dbo.wispay_payment_request (request_number)
    WHERE request_number IS NOT NULL;

IF OBJECT_ID(N'dbo.wispay_workflow_instance', N'U') IS NULL
CREATE TABLE dbo.wispay_workflow_instance (
    workflow_instance_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT PK_wispay_workflow_instance PRIMARY KEY,
    request_id UNIQUEIDENTIFIER NOT NULL,
    rule_version NVARCHAR(20) NOT NULL,
    outcome NVARCHAR(20) NOT NULL,
    current_step_sequence INT NULL,
    generated_at_utc VARCHAR(35) NOT NULL,
    payload NVARCHAR(MAX) NOT NULL
);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_wispay_workflow_instance_request'
      AND object_id = OBJECT_ID(N'dbo.wispay_workflow_instance')
)
CREATE INDEX IX_wispay_workflow_instance_request
    ON dbo.wispay_workflow_instance (request_id, generated_at_utc);

IF OBJECT_ID(N'dbo.wispay_workflow_rule', N'U') IS NULL
CREATE TABLE dbo.wispay_workflow_rule (
    rule_id INT IDENTITY(1, 1) NOT NULL
        CONSTRAINT PK_wispay_workflow_rule PRIMARY KEY,
    version NVARCHAR(20) NOT NULL,
    priority INT NOT NULL,
    request_type NVARCHAR(20) NULL,
    min_amount DECIMAL(19, 6) NULL,
    currency_code NVARCHAR(3) NULL,
    legal_entity_code NVARCHAR(40) NULL,
    department_code NVARCHAR(40) NULL,
    project_code NVARCHAR(40) NULL,
    risk_flag NVARCHAR(60) NULL,
    step_sequence INT NOT NULL,
    parallel_group NVARCHAR(40) NULL,
    approver_role NVARCHAR(60) NOT NULL,
    approver_external_identity_id NVARCHAR(80) NOT NULL,
    approver_display_name NVARCHAR(120) NOT NULL,
    approver_email NVARCHAR(160) NOT NULL,
    approver_captured_at_utc VARCHAR(35) NOT NULL,
    due_days INT NULL,
    is_active BIT NOT NULL DEFAULT (1),
    CONSTRAINT UQ_wispay_workflow_rule_row
        UNIQUE (version, priority, step_sequence, approver_external_identity_id)
);

IF OBJECT_ID(N'dbo.wispay_workflow_rule_version', N'U') IS NULL
CREATE TABLE dbo.wispay_workflow_rule_version (
    version NVARCHAR(20) NOT NULL
        CONSTRAINT PK_wispay_workflow_rule_version PRIMARY KEY,
    activated_at_utc VARCHAR(35) NOT NULL
);

IF OBJECT_ID(N'dbo.wispay_audit_event', N'U') IS NULL
CREATE TABLE dbo.wispay_audit_event (
    sequence BIGINT IDENTITY(1, 1) NOT NULL
        CONSTRAINT PK_wispay_audit_event PRIMARY KEY,
    audit_event_id UNIQUEIDENTIFIER NOT NULL,
    entity_type NVARCHAR(60) NOT NULL,
    entity_id NVARCHAR(64) NOT NULL,
    actor_external_identity_id NVARCHAR(80) NOT NULL,
    action NVARCHAR(40) NOT NULL,
    occurred_at_utc VARCHAR(35) NOT NULL,
    reason NVARCHAR(500) NULL,
    new_value NVARCHAR(MAX) NULL,
    correlation_id NVARCHAR(64) NOT NULL,
    previous_hash CHAR(64) NOT NULL,
    event_hash CHAR(64) NOT NULL,
    retention_policy_id UNIQUEIDENTIFIER NOT NULL,
    recorded_at_utc VARCHAR(35) NOT NULL,
    payload NVARCHAR(MAX) NOT NULL
);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_wispay_audit_event_correlation'
      AND object_id = OBJECT_ID(N'dbo.wispay_audit_event')
)
CREATE INDEX IX_wispay_audit_event_correlation
    ON dbo.wispay_audit_event (correlation_id, sequence);

IF OBJECT_ID(N'dbo.wispay_payment_record', N'U') IS NULL
CREATE TABLE dbo.wispay_payment_record (
    payment_record_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT PK_wispay_payment_record PRIMARY KEY,
    request_id UNIQUEIDENTIFIER NOT NULL,
    recorded_at_utc VARCHAR(35) NOT NULL,
    payload NVARCHAR(MAX) NOT NULL
);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_wispay_payment_record_request'
      AND object_id = OBJECT_ID(N'dbo.wispay_payment_record')
)
CREATE INDEX IX_wispay_payment_record_request
    ON dbo.wispay_payment_record (request_id, recorded_at_utc);
