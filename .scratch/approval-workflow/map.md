# Map — Approval workflow tracking

Feature spec: [spec.md](spec.md) · Branch: `feature/approval` · Created: 2026-08-26

## Goal

Implement the approval slice end-to-end: versioned DB-backed route generation, guarded
decision services, Reflex state adapters, `/approvals` tracking page, Azure SQL
persistence, audit evidence — following ADR-0005 seams and CONTEXT.md invariants.

## Tickets

| # | Ticket | Type | Status | Blocked by |
| --- | --- | --- | --- | --- |
| 01 | [01-sql-persistence.md](issues/01-sql-persistence.md) | task | resolved | — |
| 02 | [02-approval-services.md](issues/02-approval-services.md) | task | resolved | — |
| 03 | [03-approvals-state-and-page.md](issues/03-approvals-state-and-page.md) | task | resolved | — |
| 04 | [04-integration-e2e-browser-review.md](issues/04-integration-e2e-browser-review.md) | task | resolved | — |

Blocker resolved 2026-08-26: ODBC Driver 18 installed via winget; server public
access enabled + client IP rule added via Azure CLI. Live smoke PASS; approvals
e2e 2/2 PASS against http://127.0.0.1:3012 (isolated ports; port 3000 belongs to
the sibling auth session). Pre-existing (not this slice): committed main's wizard
Documents step renders no rows, so tests/e2e/test_request_create.py is red —
owned by the request-tracking effort's in-flight work.

## Wayfinding rules

Claim by flipping `Status:` to `claimed`; resolve with `## Answer`, status `resolved`,
and a row update here. Dependencies use `Blocked by: NN`.
