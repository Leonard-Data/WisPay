# 05 — Persistence, storage, and control integration (deferred dependencies)

Status: ready-for-human
Blocks release-to-production of the create flow, not its internal completeness.

## Context

The create step ships with real logic behind session boundaries because these platform capabilities do not exist yet (delivery-plan Phase 1/3/4 items):

1. Azure SQL repositories + unit-of-work behind `PaymentRequestService`/`AuditService` (durable requests, tamper-evident audit chain, idempotent submit keys).
2. Blob-backed document storage, malware-scan pipeline, retention/access classification enforcement (`DocumentService`).
3. Azure Document Intelligence extraction feeding vendor invoice prefill.
4. Authenticated requester identity replacing `REQUESTER_PROTOTYPE`.
5. Approval-route preview (WorkflowService, Phase 3) on Review step.
6. Queue/detail pages consuming submitted sessions (`/requests` currently honest-empty).
7. Durable drafts (explicit Save draft).

## Acceptance (when picked up)

Each numbered item lands as its own feature dir under `.scratch/` with specs referencing this file; none may silently weaken the invariants in `CONTEXT.md` (no hard deletes; audit on every transition; approved-only payment; Finance-only recording).
