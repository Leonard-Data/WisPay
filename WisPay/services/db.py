"""Azure SQL connectivity and schema bootstrap.

Physical design follows ``docs/reference/backend/data-model.md``: the app owns
tables and maps them back to the canonical logical records. Timestamp columns
store UTC ISO-8601 strings so behavior never depends on ODBC datetime parsing;
payload JSON columns remain the source of truth.

Credentials come from ``AZURE_SQL_*`` environment variables only — never
literals (CONVENTIONS.md security rules).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyodbc

_DRIVER_DEFAULT = "ODBC Driver 18 for SQL Server"

_REQUIRED_VARS = (
    "AZURE_SQL_SERVER",
    "AZURE_SQL_DATABASE",
    "AZURE_SQL_USERNAME",
    "AZURE_SQL_PASSWORD",
)

# Mirrors scripts/sql/schema.sql. Every statement is individually idempotent so
# ensure_schema can run on every cold start. Rule seeding intentionally lives in
# code (workflow_rules.seed_rules_v1 via SqlRuleStore.ensure_seeded), not DDL.
_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    IF OBJECT_ID(N'dbo.wispay_payment_request', N'U') IS NULL
    CREATE TABLE dbo.wispay_payment_request (
        request_id UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT PK_wispay_payment_request PRIMARY KEY,
        request_number NVARCHAR(32) NULL,
        lifecycle_state NVARCHAR(40) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL,
        created_at_utc VARCHAR(35) NOT NULL,
        updated_at_utc VARCHAR(35) NOT NULL
    )
    """,
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = N'UX_wispay_payment_request_number'
          AND object_id = OBJECT_ID(N'dbo.wispay_payment_request')
    )
    CREATE UNIQUE INDEX UX_wispay_payment_request_number
        ON dbo.wispay_payment_request (request_number)
        WHERE request_number IS NOT NULL
    """,
    """
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
    )
    """,
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = N'IX_wispay_workflow_instance_request'
          AND object_id = OBJECT_ID(N'dbo.wispay_workflow_instance')
    )
    CREATE INDEX IX_wispay_workflow_instance_request
        ON dbo.wispay_workflow_instance (request_id, generated_at_utc)
    """,
    """
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
    )
    """,
    """
    IF OBJECT_ID(N'dbo.wispay_workflow_rule_version', N'U') IS NULL
    CREATE TABLE dbo.wispay_workflow_rule_version (
        version NVARCHAR(20) NOT NULL
            CONSTRAINT PK_wispay_workflow_rule_version PRIMARY KEY,
        activated_at_utc VARCHAR(35) NOT NULL
    )
    """,
    """
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
    )
    """,
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = N'IX_wispay_audit_event_correlation'
          AND object_id = OBJECT_ID(N'dbo.wispay_audit_event')
    )
    CREATE INDEX IX_wispay_audit_event_correlation
        ON dbo.wispay_audit_event (correlation_id, sequence)
    """,
)


def connection_string() -> str:
    """Assemble an ODBC connection string from ``AZURE_SQL_*`` variables."""
    values = {name: os.getenv(name, "") for name in _REQUIRED_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        hint = (
            "Copy .env.example to .env and fill the AZURE_SQL_* values "
            "(see AGENTS.md quick start)."
        )
        raise RuntimeError(
            f"Missing Azure SQL environment variables: {', '.join(missing)}. {hint}"
        )
    driver = os.getenv("AZURE_SQL_DRIVER", _DRIVER_DEFAULT)
    encrypt = os.getenv("AZURE_SQL_ENCRYPT", "yes")
    trust_cert = os.getenv("AZURE_SQL_TRUST_SERVER_CERTIFICATE", "no")
    server = values["AZURE_SQL_SERVER"].removeprefix("tcp:")
    return (
        f"Driver={{{driver}}};"
        f"Server=tcp:{server},1433;"
        f"Database={values['AZURE_SQL_DATABASE']};"
        f"Uid={values['AZURE_SQL_USERNAME']};"
        f"Pwd={values['AZURE_SQL_PASSWORD']};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
        "ConnectRetryCount=3;"
        "ConnectRetryInterval=10;"
        "Connection Timeout=30;"
    )


def connect() -> pyodbc.Connection:
    """Open an Azure SQL connection; failures carry an actionable setup hint."""
    try:
        import pyodbc

        return pyodbc.connect(connection_string(), timeout=30)
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to Azure SQL. Check the AZURE_SQL_* values, confirm "
            f"'{_DRIVER_DEFAULT}' is installed, and allow this machine's public IP "
            "in the server's networking/firewall settings."
        ) from exc


def ensure_schema(conn: pyodbc.Connection) -> None:
    """Create any missing ``dbo.wispay_*`` tables and indexes. Idempotent."""
    cursor = conn.cursor()
    try:
        for statement in _SCHEMA_STATEMENTS:
            cursor.execute(statement)
    finally:
        cursor.close()
    conn.commit()


def schema_statements() -> tuple[str, ...]:
    """Expose the managed DDL statements (used by tests and tooling)."""
    return _SCHEMA_STATEMENTS
