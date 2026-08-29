"""Database connectivity and schema bootstrap for the WisPay app.

Supports two drivers behind one ``Stores`` Protocol (ADR-0004 / BE-1):

1. **Azure SQL** — production durability. Tables map the canonical logical
   records from ``docs/reference/backend/data-model.md``; timestamps are stored
   as UTC ISO-8601 strings so behavior never depends on ODBC datetime parsing;
   payload JSON columns remain the source of truth.
2. **SQLite** — dev / CI. Same logical records, same payload shape, but stored
   in a local file (or ``:memory:``) using the standard library. No external
   driver required.

Driver selection reads ``WS_DB_URL`` first; the canonical defaults are:

- ``sqlite:///wispay.db`` (relative to the working directory) for dev / CI
  when no Azure credentials are present.
- ``mssql+pyodbc://...`` (assembled from ``AZURE_SQL_*`` env vars) for
  production.

Credentials come from environment variables only — never literals
(CONVENTIONS.md security rules).
"""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pyodbc

    from WisPay.services.repositories import Stores

DriverKind = Literal["sqlite", "azure-sql"]

#: Default dev URL when ``WS_DB_URL`` is unset and no Azure env is configured.
DEFAULT_SQLITE_URL = "sqlite:///wispay.db"

_DRIVER_DEFAULT = "ODBC Driver 18 for SQL Server"

_AZURE_REQUIRED_VARS = (
    "AZURE_SQL_SERVER",
    "AZURE_SQL_DATABASE",
    "AZURE_SQL_USERNAME",
    "AZURE_SQL_PASSWORD",
)

#: Detect whether Azure SQL env vars are present (used to pick the default
#: driver when ``WS_DB_URL`` is not set).
_AZURE_VARS_FOR_DETECT = ("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE")


# Mirrors scripts/sql/schema.sql. Every statement is individually idempotent so
# ensure_schema can run on every cold start. Rule seeding intentionally lives in
# code (workflow_rules.seed_rules_v1 via SqlRuleStore.ensure_seeded), not DDL.
_AZURE_SCHEMA_STATEMENTS: tuple[str, ...] = (
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
    """
    IF OBJECT_ID(N'dbo.wispay_payment_record', N'U') IS NULL
    CREATE TABLE dbo.wispay_payment_record (
        payment_record_id UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT PK_wispay_payment_record PRIMARY KEY,
        request_id UNIQUEIDENTIFIER NOT NULL,
        recorded_at_utc VARCHAR(35) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL
    )
    """,
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = N'IX_wispay_payment_record_request'
          AND object_id = OBJECT_ID(N'dbo.wispay_payment_record')
    )
    CREATE INDEX IX_wispay_payment_record_request
        ON dbo.wispay_payment_record (request_id, recorded_at_utc)
    """,
)


def _detect_azure_env() -> bool:
    """True when the two minimum Azure SQL env vars are populated."""
    return all(os.getenv(name) for name in _AZURE_VARS_FOR_DETECT)


def driver_kind_from_url(url: str) -> DriverKind:
    """Return the driver kind implied by a SQLAlchemy-style URL.

    Accepts ``sqlite:///...`` (including ``:memory:``) and any
    ``mssql+pyodbc://...`` / ``mssql://...`` URL. Other schemes raise.
    """
    lowered = url.strip().lower()
    if lowered.startswith("sqlite:"):
        return "sqlite"
    if lowered.startswith("mssql") or lowered.startswith("sqlserver:"):
        return "azure-sql"
    raise ValueError(
        f"Unsupported WS_DB_URL scheme: {url!r}. "
        "Use 'sqlite:///path/to.db' (dev) or 'mssql+pyodbc://...' (Azure SQL)."
    )


def default_db_url() -> str:
    """Resolve the effective DB URL.

    Precedence:

    1. ``WS_DB_URL`` if set.
    2. Azure SQL assembly from ``AZURE_SQL_*`` env vars if those are populated.
    3. ``DEFAULT_SQLITE_URL`` for dev / CI.
    """
    explicit = os.getenv("WS_DB_URL")
    if explicit:
        return explicit
    if _detect_azure_env():
        return _azure_sqlalchemy_url()
    return DEFAULT_SQLITE_URL


def driver_kind() -> DriverKind:
    """Return the active driver kind for the current process."""
    return driver_kind_from_url(default_db_url())


# --------------------------------------------------------------------------- #
# Azure SQL
# --------------------------------------------------------------------------- #


def connection_string() -> str:
    """Assemble an ODBC connection string from ``AZURE_SQL_*`` variables."""
    values = {name: os.getenv(name, "") for name in _AZURE_REQUIRED_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        hint = (
            "Copy .env.example to .env and fill the AZURE_SQL_* values (see AGENTS.md quick start)."
        )
        raise RuntimeError(f"Missing Azure SQL environment variables: {', '.join(missing)}. {hint}")
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


def _azure_sqlalchemy_url() -> str:
    """Assemble a SQLAlchemy URL for Azure SQL (used by ``rxconfig``)."""
    values = {name: os.getenv(name, "") for name in _AZURE_REQUIRED_VARS}
    if not all(values.values()):
        missing = [n for n, v in values.items() if not v]
        raise RuntimeError("Missing Azure SQL environment variables: " + ", ".join(missing))
    server = values["AZURE_SQL_SERVER"].removeprefix("tcp:")
    return (
        f"mssql+pyodbc://{values['AZURE_SQL_USERNAME']}:{values['AZURE_SQL_PASSWORD']}"
        f"@{server}.database.windows.net/{values['AZURE_SQL_DATABASE']}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Encrypt=yes"
        "&TrustServerCertificate=no"
        "&Connection+Timeout=30"
    )


def azure_connect() -> pyodbc.Connection:
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


def ensure_azure_schema(conn: pyodbc.Connection) -> None:
    """Create any missing ``dbo.wispay_*`` tables and indexes. Idempotent."""
    cursor = conn.cursor()
    try:
        for statement in _AZURE_SCHEMA_STATEMENTS:
            cursor.execute(statement)
    finally:
        cursor.close()
    conn.commit()


def azure_schema_statements() -> tuple[str, ...]:
    """Expose the Azure SQL DDL statements (used by tests and tooling)."""
    return _AZURE_SCHEMA_STATEMENTS


# --------------------------------------------------------------------------- #
# SQLite
# --------------------------------------------------------------------------- #


def _sqlite_path(url: str) -> str:
    """Resolve a ``sqlite:///`` URL to a filesystem path or ``:memory:``."""
    body = url[len("sqlite:") :].lstrip("/")
    if not body:
        raise ValueError(f"WS_DB_URL is missing the SQLite path: {url!r}")
    return body


def sqlite_connect(url: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection from a ``sqlite:///...`` URL (or default)."""
    target_url = url if url is not None else default_db_url()
    if not target_url.lower().startswith("sqlite:"):
        raise ValueError(f"sqlite_connect requires a sqlite:// URL, got {target_url!r}")
    path = _sqlite_path(target_url)
    # ``check_same_thread=False`` mirrors pyodbc's per-call cursor model and is
    # safe because ``WisPay`` always uses a single connection per process (see
    # ``runtime.stores``). WAL improves concurrent reads and survives crashes.
    conn = sqlite3.connect(path, check_same_thread=False)
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def sqlite_connect_in_memory() -> sqlite3.Connection:
    """Return a private in-memory SQLite connection.

    Used by tests and tooling that need an isolated scratchpad. The connection
    is private to the caller (not the shared ``:memory:`` cache) so each test
    sees a fresh schema.
    """
    return sqlite_connect("sqlite:///:memory:")


# --------------------------------------------------------------------------- #
# Public API used by ``runtime`` and tests
# --------------------------------------------------------------------------- #


def ensure_schema(conn: object) -> None:
    """Dispatch schema bootstrap to the right driver.

    Accepts either a ``pyodbc.Connection`` (Azure SQL) or a
    ``sqlite3.Connection`` (dev). The function inspects the connection type
    rather than relying on driver kind at the call site so callers that
    already hold a connection do not need to thread the URL through.
    """
    if isinstance(conn, sqlite3.Connection):
        from WisPay.services.sqlite_repositories import ensure_sqlite_schema

        ensure_sqlite_schema(conn)
        return
    ensure_azure_schema(conn)


def schema_statements() -> tuple[str, ...]:
    """Expose the Azure SQL DDL statements (kept for back-compat with existing tests)."""
    return _AZURE_SCHEMA_STATEMENTS


def connect() -> object:
    """Open a connection using the active driver.

    Returns a ``pyodbc.Connection`` (Azure SQL) or ``sqlite3.Connection``
    (dev). Callers that need driver-specific behavior branch on the runtime
    ``driver_kind()``; everything else just uses the ``Stores`` Protocol.
    """
    if driver_kind() == "sqlite":
        return sqlite_connect()
    return azure_connect()


def stores(*, ensure_tables: bool = True) -> Stores:
    """Return a live ``Stores`` bundle using the active driver.

    Mirrors the legacy ``sql_repositories.sql_stores`` entry point so callers
    (notably ``WisPay.py`` lifespan) do not need to know which driver is in
    use. ``ensure_tables`` is honored for both drivers.
    """
    if driver_kind() == "sqlite":
        from WisPay.services.sqlite_repositories import sqlite_stores

        return sqlite_stores(ensure_tables=ensure_tables)
    from WisPay.services.sql_repositories import sql_stores

    conn = azure_connect()
    return sql_stores(conn, ensure_tables=ensure_tables)
