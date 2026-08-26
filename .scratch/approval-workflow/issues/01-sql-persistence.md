# 01 — SQL persistence layer (db, repositories, schema)

Status: claimed
Feature: `.scratch/approval-workflow/spec.md` (read first — contracts pinned there)

## Target

New files only:
- `WisPay/services/db.py`
- `WisPay/services/repositories.py`
- `WisPay/services/sql_repositories.py`
- `scripts/sql/schema.sql`
- `tests/services/fakes.py`
- `tests/services/test_db.py`
- `tests/services/test_sql_repositories.py`

Do NOT touch: `WisPay/models/*`, `states/*`, `pages/*`, `routers.py`, existing services except reading them.

## Change

Implement exactly the protocol/bundle contracts in spec §"Store protocols + SQL infra":
`RequestStore`, `WorkflowStore`, `AuditEventStore`, `RuleStore` protocols; `Stores` bundle;
SQL implementations (`sql_stores(conn)`), `DurableAuditTrail`; `connection_string()`,
`connect()`, `ensure_schema()` in `db.py`; schema DDL in `scripts/sql/schema.sql` mirroring
`ensure_schema` (prefix `dbo.wispay_*`, idempotent `IF OBJECT_ID(...) IS NULL`, seed rules v1
inserted only when absent). Payload columns use Pydantic `model_dump_json` /
`model_validate_json`. Parameterized queries only.

Rules: stdlib + pyodbc + `WisPay.models` + `audit_trail` helpers (`GENESIS_HASH`,
`canonical_payload`, `chain_hash`) only — no Reflex, no env access outside `db.py`.
`DurableAuditTrail.append` mirrors the `InMemoryAuditTrail.append` signature (read it) but
chains over `store.last_event_hash()` and persists through the store; never duplicate chain
math. All datetimes timezone-aware (`DATETIMEOFFSET`). `mypy --strict` and ruff clean,
line length 100, no prints.

## Tests (no skips)

Fakes in `tests/services/fakes.py` implement all four protocols in memory (`FakeStores`).
Cover at minimum: request save/get round trip incl. re-save upsert; instance save with steps +
`latest_instance_for_request` + `pending_instances` ordering/filtering; rule store active
version + rules; audit append ordering + `events_for_request` filter; `last_event_hash`
genesis when empty; `DurableAuditTrail` chain continues across two trail instances over one
store and `verify()`-style recomputation passes (reuse `chain_hash`). SQL-specific code paths
(`ensure_schema` statement list, connection string assembly from env incl. driver default)
tested without a server: assert statement text contains expected table names/idsempotency
guards and connstr parts; live connectivity is ticket 04's smoke, not skipped tests here.

## Acceptance

- `uv run pytest tests/services -q` green.
- `uv run ruff check WisPay/services scripts tests && uv run ruff format --check ...` clean.
- `uv run mypy WisPay` strict-clean.
