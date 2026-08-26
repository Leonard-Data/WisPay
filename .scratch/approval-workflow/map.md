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
| 04 | [04-integration-e2e-browser-review.md](issues/04-integration-e2e-browser-review.md) | task | needs-triage | 01, 02, 03 |

External blocker (environment, not code): Azure SQL reachability — ODBC Driver 18 missing
on workstation and login timed out (`scripts/test_connections.py --db-only` FAIL 2026-08-26).
Ticket 04's live-SMOKE acceptance waits on this; everything else proceeds against fakes.

## Wayfinding rules

Claim by flipping `Status:` to `claimed`; resolve with `## Answer`, status `resolved`,
and a row update here. Dependencies use `Blocked by: NN`.
