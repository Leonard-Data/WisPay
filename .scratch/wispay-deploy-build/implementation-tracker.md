# WisPay Deploy Build — Implementation Tracker

**Document type:** Build contract for the `wispay-deploy-readiness` AgentTeams engagement
**Scope:** Spec + design lock (BS-1) → t1 deliverable. Downstream tasks t2–t6 consume this contract.
**Repo:** `E:\projects\WisPay` (Reflex 0.9.8, Python 3.14, Pydantic v2)
**Source of truth repos:** `E:\projects\WisPay-doc` (canonical domain) and `E:\projects\WisPay-deisgn` (ElevenLabs-bound design system)
**Owner:** `backend-engineer` (AgentTeams worker)
**Status:** BS-1 — locked spec; downstream tasks must conform to the contracts in §5, §6, §7.
**Retrieval date for design sources:** 2026-08-29

---

## 1. Authoritative sources read

| Source | Path | Role |
| --- | --- | --- |
| Domain glossary & invariants | `E:\projects\WisPay-doc\CONTEXT.md` | Canonical glossary, 14-state lifecycle, 10 core invariants, scope boundary, repository separation |
| Delivery plan | `E:\projects\WisPay-doc\wispay-delivery-plan.md` | Phased plan (0–7), release gates, "Done when" criteria |
| ADR-0001: Repo separation | `WisPay-doc\docs\adr\0001-docs-app-repo-separation.md` | Doc vs. app ownership (boundary confirmed) |
| ADR-0002: Reflex Python | `WisPay-doc\docs\adr\0002-reflex-python.md` | Framework choice + pre-v1 mitigation (services outside Reflex State) |
| ADR-0003: Hybrid matching | `WisPay-doc\docs\adr\0003-hybrid-matching.md` | 70/90% confidence thresholds; `WISPAY_AUTO_MATCH_THRESHOLD` env knob |
| ADR-0004: Canonical data model | `WisPay-doc\docs\adr\0004-canonical-data-model-strategy.md` | Logical model lives in docs; physical DDL lives in app; mandated 18 record types; cross-cutting rules (1–5) |
| ADR-0005: Service–State seam | `WisPay-doc\docs\adr\0005-service-reflex-state-seam.md` | Services do not import `reflex`; Reflex State is a thin UI adapter; 14 initial service families |
| ADR-0006: Versioned lifecycle state machine | `WisPay-doc\docs\adr\0006-versioned-lifecycle-state-machine.md` | 14 canonical states, transition guards, frozen route snapshots, invalidation trigger fields |
| ADR-0007: AuthN/AuthZ model | `WisPay-doc\docs\adr\0007-authentication-authorization-model.md` | SSO + role-based, 8 canonical roles, SoD controls (1–6) |
| ADR-0008: API surface | `WisPay-doc\docs\adr\0008-api-surface.md` | Two surfaces: UI event handlers + integration routes (versioned, idempotent) |
| Workflow research | `WisPay-doc\docs\research\payment-request-workflow.md` | Six control stages; retention legally approved only; Vietnam-first |
| Visual implementation contract | `E:\projects\WisPay\docs\product\DESIGN.md` | App-side snapshot of `WisPay-deisgn\DESIGN.md` |
| Design tokens (source-backed) | `E:\projects\WisPay\assets\design-tokens.css` (mirrored from `WisPay-deisgn\assets\tokens.css`) | Six portable foundation tokens (`--ws-bg/surface/fg/muted/border/accent`) + supporting values |
| Prototype PRD | `E:\projects\WisPay-deisgn\wispay-prd.md` | Source of A1–A14 acceptance criteria + 7 OPEN questions |
| App coding conventions | `E:\projects\WisPay\CONVENTIONS.md` | Python style, components, Reflex patterns, Pydantic rules, security/audit invariants, testing |
| App agent rules | `E:\projects\WisPay\AGENTS.md` | Source-of-truth pointers, domain-model rules, UI rules, validation gate |
| App repo state | Existing `WisPay/`, `WisPay\models\`, `WisPay\services\`, `WisPay\pages\`, `WisPay\components\`, `WisPay\layout\`, `WisPay\routers.py`, `WisPay\WisPay.py`, `rxconfig.py`, `tests\`, `assets\`, `pyproject.toml`, `.env.example`, `.pre-commit-config.yaml`, `scripts\validate.sh` | Implementation baseline |

### 1.1 Environment note (must surface, not silently fix)

`AGENTS.md` references `C:\Users\binh.phung\projects\WisPay-Design-System`; on this machine the design-system source lives at `E:\projects\WisPay-deisgn\` (directory name misspelled in the prompt history). Substance matches the checked-in `docs\product\DESIGN.md` snapshot. **Recorded as a sync gap, not a conflict**, per the convention from `.scratch\payment-request-create\spec.md`.

---

## 2. CONTEXT.md invariants — cited verbatim and operationalized

Every invariant below is a verbatim quote of `WisPay-doc\CONTEXT.md` § "Core invariants". Each row shows where in code it is enforced and where it is tested. A green dot (●) marks invariants already wired into the existing code; a hollow dot (○) marks invariants pending the work in §6 / §7.

| # | Invariant (verbatim quote) | Operationalized in code | Tests |
| --- | --- | --- | --- |
| 1 | "Every request has one unique request number, one request type, one requester, one beneficiary, and one legal entity." | ● `WisPay\models\payment_request.py` (`PaymentRequest` invariants + `validate_request_identity_and_type`). | ● `tests\models\test_payment_request.py`. |
| 2 | "A request cannot be submitted without required fields and documents for its type and subtype." | ● `WisPay\services\request_creation.py` blocks on missing documents via the provisional matrix in `WisPay\services\reference_data.py::doc_requirements`. | ● `tests\services\test_request_creation.py`. ○ Add regression when matrix grows in t2. |
| 3 | "The requester cannot provide final approval for their own request." | ● `WisPay\services\approval_workflow.py` (SoD guard: actor != requester on `APPROVAL_PENDING → APPROVED` path). | ● `tests\services\test_approval_workflow.py`. |
| 4 | "Approval routes are generated from versioned rules and preserved with the request." | ● `WisPay\models\workflow.py` (`WorkflowInstance.rule_version`), `WisPay\services\workflow_rules.py::seed_rules_v1`, `SqlRuleStore.ensure_seeded`. | ● `tests\services\test_workflow_rules.py`, `tests\services\test_sql_repositories.py`. |
| 5 | "All submissions, reviews, approvals, rejections, changes, delegation actions, and payment updates are audit logged." | ● `WisPay\services\audit_trail.py` (`InMemoryAuditTrail` chain + verification), `WisPay\services\sql_repositories.py` durable `AuditEvent` append. | ● `tests\services\test_audit_trail.py`. ○ Durable SQL path coverage added in t2/t5. |
| 6 | "Vendor evidence uses three-way matching when PO and receipt data apply; employee evidence uses receipt, policy, and advance reconciliation instead." | ● `WisPay\models\documents.py` (`MatchConfidence`, `MatchProposal`, `HumanReviewResult`). ○ Hybrid matching rule engine (70/90%) lands in t2. | ○ `tests\services\test_matching.py` (added in t2). |
| 7 | "Only an approved request can enter payment processing." | ● `WisPay\models\lifecycle.py` (`APPROVED → PAYMENT_IN_PROCESS` in `NORMAL_TRANSITIONS`; no shortcut path). | ● `tests\models\test_lifecycle.py`. |
| 8 | "Only authorized Finance users can record payment completion." | ○ `WisPay\services\payment_recording.py` (planned, see §7). | ○ `tests\services\test_payment_recording.py` (planned t3). |
| 9 | "The MVP records external payment completion but does not send money." | ● Copy contract enforced via `WisPay\styles.py` voice rules + page copy. ○ `payment_recording` service uses literal "recorded", "external reference" — never "transfer" / "debit" / "sent". | ○ Copy assertions added in t6 validation gate. |
| 10 | "Submitted financial records and audit events are not hard-deleted through normal application functions." | ● `RequestStore.save` / `AuditEventStore.append` (no delete methods). Repository `Protocol`s expose `save`/`get` only. | ● `tests\services\test_sql_repositories.py`. |

### 2.1 14-state lifecycle (ADR-0006) — current source of truth

The 14 canonical states already exist in `WisPay\models\lifecycle.py::LifecycleState` and are wired into `DECLARED_TRANSITIONS`. Coverage in §4.

---

## 3. Files in the WisPay repo that will be touched

Legend: ✚ new file · ✎ edit existing · ✓ already in place (no edit needed for BS-1 contract but downstream tasks may refine)

### 3.1 t1 — Spec + design lock (this task, BS-1)

| Path | Action | Reason |
| --- | --- | --- |
| `.scratch\wispay-deploy-build\implementation-tracker.md` | ✚ | This document. |
| `WisPay\models\__init__.py` | ✓ | Already exports `CANONICAL_RECORD_TYPES`. Used as-is in §5 contracts. |
| `WisPay\models\lifecycle.py` | ✓ | `DECLARED_TRANSITIONS` covers all 14 states; see §4 matrix. |
| `WisPay\models\enums.py` | ✓ | Source of `LifecycleState`-adjacent enums used in §5. |
| `WisPay\services\repositories.py` | ✓ | `Protocol` contracts in §5 use existing shapes. |

### 3.2 t2 — SQLite dev switch + dual-driver stores (BE-1)

| Path | Action | Reason |
| --- | --- | --- |
| `pyproject.toml` | ✎ | Add `sqlite` driver / conditional extra so `pyodbc` is no longer a hard requirement for dev. Keep `pyodbc` for production. |
| `WisPay\services\db.py` | ✎ | Add `_sqlite_connection_string()` and `driver_kind` enum; route to SQLite when `WISPAY_DB_URL` is set, else Azure SQL with current env vars. `ensure_schema` gets a parallel SQLite DDL block (the existing `wispay_*` DDL becomes the production source; SQLite DDL is a parallel scaffold — single source of truth per ADR-0004). |
| `WisPay\services\repositories.py` | ✎ | Existing `Protocol` set already driver-agnostic; no edits required. Confirm docstring note. |
| `WisPay\services\sql_repositories.py` | � | Rename to `sql_repositories.py` keeps the Azure-SQL path as one of two implementations; add `sqlite_repositories.py` sibling that satisfies the same `Stores` Protocol using `sqlite3` stdlib + parameterized statements. |
| `WisPay\services\sqlite_repositories.py` | ✚ | New sibling module. UUIDs stored as text; `payload` JSON columns identical to SQL path. `ensure_schema` reuses `db._SQLITE_SCHEMA_STATEMENTS`. |
| `WisPay\services\runtime.py` | ✎ | Branch on `driver_kind`: SQLite cached as plain module-singleton (no broken-link recovery needed). Azure SQL caching logic preserved. |
| `WisPay\WisPay.py` | ✎ | Lifespan task remains `runtime.stores()`; driver choice becomes env-driven. |
| `rxconfig.py` | ✎ | Default `db_url` switches to `sqlite:///./wispay-dev.db` when `WISPAY_DB_URL` is unset and no `AZURE_SQL_*` vars are populated. When Azure SQL env is populated, the existing connection string is used. Document the precedence in a comment. |
| `.env.example` | ✎ | Add `WISPAY_DB_URL=sqlite:///./wispay-dev.db` (commented) and clarify that Azure SQL env vars remain production-only. |
| `WisPay\services\workflow_rules.py` | ✓ | Rule seeds remain code-defined; works on both drivers. |
| `WisPay\services\db.py` (test) | ✓ | Existing `tests\services\test_db.py` already exercises Azure SQL connection-string assembly; new `tests\services\test_db_sqlite.py` covers the dev path. |
| `scripts\validate.sh` | ✎ | Add an optional `WISPAY_VALIDATE_DRIVER=sqlite` env knob for the gate. Default remains Azure SQL (matches production). |
| `.gitignore` | ✎ | Add `wispay-dev.db`, `*.db` patterns are already noted in `CONVENTIONS.md`; reaffirm. |

### 3.3 t3 — Service layer wired to stores (BE-2)

| Path | Action | Reason |
| --- | --- | --- |
| `WisPay\services\payment_recording.py` | ✚ | Implements `PaymentRecordingService.record(...)` per §7 / §5 A6. Owns AuthZ + audit + transition guard for `PAYMENT_IN_PROCESS → PAID`. |
| `WisPay\services\budget_review.py` | ✚ | Pure-Python budget math (`Within Budget` / `Over Budget — Exception Required` / `Not Applicable`) + persistence via `Stores`. |
| `WisPay\services\compliance_review.py` | ✚ | Three-way match orchestration for Vendor + checklist answer recording for both families. |
| `WisPay\services\evidence_validation.py` | ✚ | Calls into `WisPay\services\matching.py` (70/90% thresholds, ADR-0003) and persists `MatchDecision`. |
| `WisPay\services\matching.py` | ✚ | Pure-Python confidence scoring using amount + description + UoM signals. Reads `WISPAY_AUTO_MATCH_THRESHOLD` env. |
| `WisPay\services\lifecycle_service.py` | ✚ | `LifecycleService.transition(request_id, to_state, actor)` centralizes transition guards + invalidation trigger handling (ADR-0006). Calls `audit_trail` and `repositories`. |
| `WisPay\services\workflow_routing.py` | ✎ | Already exists in `approval_workflow.py`; consolidate name to `workflow_routing.py` if needed for clarity, otherwise keep `approval_workflow.py`. |
| `WisPay\services\notification.py` | ✚ | In-app notification dispatch; channel = `IN_APP` (ADR-0007 §"Non-decisions" keeps email out of MVP scope). |
| `WisPay\services\comments.py` | ✚ | Threaded comments + @mention parsing. |
| `WisPay\services\report.py` | ✚ | Success-measure panel computations (A11 + acceptance checks). |
| `WisPay\services\runtime.py` | ✎ | No driver change in t3; only consumed by new services. |
| `tests\services\test_payment_recording.py` | ✚ | SoD, invariant 7, invariant 8. |
| `tests\services\test_lifecycle_service.py` | ✚ | Invalidations + transition guards per ADR-0006. |
| `tests\services\test_matching.py` | ✚ | Hybrid matching 70/90% thresholds. |
| `tests\services\test_budget_review.py` | ✚ | Over-budget exception flow. |
| `tests\services\test_compliance_review.py` | ✚ | Three-way match happy + exception + N/A-with-reason. |

### 3.4 t4 — Components + 11 product surfaces (UI-1)

| Path | Action | Reason |
| --- | --- | --- |
| `WisPay\components\navigation\sidebar.py` | � | Already exists; confirm 264px desktop width + drawer <1024px + footer persona switcher. |
| `WisPay\components\navigation\mobile_bar.py` | ✚ | Mobile bar (menu, language, notifications, brand). |
| `WisPay\components\cards.py` | ✚ | `.card`, `.card-inset`, `.card-warm` wrappers (currently in `WisPay\styles.py::Styles` as raw `rx.Style`; promote to reusable component functions per `CONVENTIONS.md#Components`). |
| `WisPay\components\status_pill.py` | ✚ | `status_pill(kind, label)` component. |
| `WisPay\components\table.py` | ✚ | `data_table(columns, rows, mobile_cards=...)` honoring `data-th` responsive collapse. |
| `WisPay\components\banner.py` | ✚ | Banner (danger/warn/info/success) full-width message row. |
| `WisPay\components\lifecycle_stepper.py` | ✚ | Numbered nodes + completed (black), active (focus ring), returned/rejected/cancelled branches. |
| `WisPay\components\waveform_amount_strip.py` | ✚ | One expressive flourish per `DESIGN.md` §3; never decorative; paired with plain gross + text description. |
| `WisPay\components\tabs.py` | ✚ | Horizontal tab row, mono count badges, scroll-on-small. |
| `WisPay\components\empty_state.py` | ✚ | Empty + loading + error patterns. |
| `WisPay\components\toast.py` | ✚ | Dark toasts with danger variant for errors. |
| `WisPay\layout\shell.py` | ✎ | Already exists; verify sidebar grouping (Workspace / Review / Operations / Governance) and guided flow panel. |
| `WisPay\layout\general.py` | ✓ | Existing helpers, no edit. |
| `WisPay\pages\dashboard.py` | ✎ | Persona-aware widgets (8 personas, A13). |
| `WisPay\pages\requests.py` | ✎ | Search + filter workspace; saved views per persona (A1). |
| `WisPay\pages\request_new\wizard_page.py` | ✎ | Wizard 4-step Type → Details → Documents → Review & Submit (A1). |
| `WisPay\pages\request_detail.py` | � | Header + banner zone + stepper + 5 tabs + action bar (A2/A4/A5/A6/A7). |
| `WisPay\pages\approvals.py` | � | Approval queue + decision drawer + reason modals (A2). |
| `WisPay\pages\finance_review.py` | ✚ | Compliance / budget / duplicate / cancel / close queue (A2/A5). |
| `WisPay\pages\payments.py` | ✚ | Operator queue with Start / Record / Close actions (A6). |
| `WisPay\pages\admin.py` | ✚ | Sample configuration studio + route simulator (A3). |
| `WisPay\pages\audit.py` | ✚ | Read-only audit search + expandable diff rows (A14). |
| `WisPay\pages\reports.py` | ✚ | Success-measure panel + spend analysis + export center (A11). |
| `WisPay\styles.py` | ✎ | Add `Tokens.WAVE_BAR_*` for the waveform strip; promote `Styles.card` into a component rather than a raw style. |
| `assets\design-tokens.css` | ✎ | Sync any new tokens introduced by the design source on a recorded retrieval date. |
| `assets\layout.css` / `assets\globals.css` | ✎ | Add `data-th` mobile-table rules + lifecycle stepper rules + waveform strip CSS. |
| `WisPay\pages\errors.py` | ✎ | Confirm 404/500/503 already wire copy correctly. |
| `WisPay\routers.py` | ✎ | Add `/finance-review`, `/payments`, `/admin`, `/audit`, `/reports` routes; `/503` already exists. |

### 3.5 t5 — States, auth, routing, demo seed (ST-1)

| Path | Action | Reason |
| --- | --- | --- |
| `states\auth_state.py` | ✎ | Already exists; confirm Entra (ADR-0007) SSO + persona switching. |
| `states\persona_state.py` | ✚ | Persona switcher that swaps nav, queues, data scope. |
| `states\dashboard_state.py` | ✚ | Persona-aware widget data. |
| `states\requests_state.py` | ✚ | Search, filter, saved-view persistence. |
| `states\request_new_state.py` | ✎ | Already exists; verify 4-step state machine. |
| `states\request_tracking_state.py` | ✎ | Already exists; refresh on detail load. |
| `states\approvals_state.py` | ✎ | Already exists. |
| `states\finance_review_state.py` | ✚ | Queue + actions. |
| `states\payments_state.py` | � | Start/Record/Close actions. |
| `states\admin_state.py` | � | Sample configuration + route simulator. |
| `states\audit_state.py` | ✚ | Read-only audit search. |
| `states\reports_state.py` | ✚ | Success-measure + spend analysis + exports. |
| `states\notifications_state.py` | ✚ | Unread bell + recent-audit ticker. |
| `states\i18n_state.py` | ✚ | EN/VI dictionary + persistence (A9). |
| `WisPay\services\demo_seed.py` | ✚ | Deterministic fixtures for 8 personas + ~15 requests (S01–S16 per PRD §9) + 3-month budget snapshots + 1 active delegation + pre-seeded notifications/comments. Honors "fixed reference date" 2026-08-24 for overdue/SLA math. |
| `WisPay\services\user_context.py` | ✎ | Already exists; thread persona context into services. |
| `WisPay\services\authentication.py` | ✎ | Already exists; ensure Entra token → `UserSnapshot` mapping. |
| `WisPay\routers.py` | ✎ | Add `on_load` hooks for each new page (load queue / refresh). |

### 3.6 t6 — Validation + e2e + deploy artifact (REL-1)

| Path | Action | Reason |
| --- | --- | --- |
| `scripts\validate.sh` | ✎ | Add `WISPAY_VALIDATE_DRIVER=sqlite uv run pytest` as the gate default for dev, with `WISPAY_VALIDATE_DRIVER=azure` for production runs. |
| `tests\e2e\conftest.py` | ✎ | Already exists; add explicit ports (frontend 3000 / backend 8000 / host 127.0.0.1) per AGENTS.md UI validation rule. |
| `tests\e2e\test_ui_smoke.py` | ✎ | Existing. |
| `tests\e2e\test_a1_vendor_submit.py` | ✚ | Missing required doc blocks submission. |
| `tests\e2e\test_a2_happy_path.py` | ✚ | Approve → budget → compliance → route complete → Approved. |
| `tests\e2e\test_a3_over_budget.py` | ✚ | Over-budget exception + CFO append + frozen route invariant. |
| `tests\e2e\test_a4_return_edit_invalidate.py` | ✚ | Return → amount change → downstream invalidated → audit old/new. |
| `tests\e2e\test_a5_duplicate_resolve.py` | ✚ | Duplicate pair + resolution. |
| `tests\e2e\test_a6_payment_record.py` | ✚ | Operator cannot start before route complete; amount-match guardrail; proof + external ref → Paid. |
| `tests\e2e\test_a7_settlement.py` | ✚ | Settlement links S06 + balance math + 30-day warning. |
| `tests\e2e\test_a8_refresh_persist.py` | ✚ | Refresh preserves full state. |
| `tests\e2e\test_a9_i18n.py` | ✚ | EN↔VI switch persists. |
| `tests\e2e\test_a10_responsive.py` | ✚ | No horizontal scroll at 360/390/430/600/768/820/1024/1366/1440/1920. |
| `tests\e2e\test_a11_csv_export.py` | ✚ | CSV downloads with UTF-8 BOM; permission-scoped. |
| `tests\e2e\test_a12_money_movement_copy.py` | ✚ | Zero copy implies WisPay initiates money movement. |
| `tests\e2e\test_a13_persona_nav.py` | ✚ | 8 personas see correct nav + disabled-with-reason. |
| `tests\e2e\test_a14_audit_immutable.py` | ✚ | Consequential action appears in audit stream immutably. |
| `Dockerfile` | ✚ | Reflex container build for Azure Container Apps / App Service. |
| `azure-deploy.bicep` | ✚ | IaC for production Azure SQL + Reflex app. (ADR-0008: integration routes are versioned; document the surface.) |
| `README.md` | ✎ | Document SQLite dev path, Azure SQL prod path, demo seed reset, deploy steps. |
| `pyproject.toml` | ✎ | Add `[project.optional-dependencies]` for `azure-sql`, `sqlite`, `dev`. |

### 3.7 Reference docs to read (no edits)

`WisPay-doc\docs\reference\backend\data-model.md`, `WisPay-doc\docs\reference\backend\lifecycle-state-machine.md`, `WisPay-doc\docs\reference\backend\service-layer.md`, `WisPay-doc\docs\reference\backend\authz-rbac.md`, `WisPay-doc\docs\reference\backend\api-surface.md` — already named in `AGENTS.md` "Domain model source rules". The existing code in `WisPay\models\`, `WisPay\services\` already conforms; new files in t3 reuse these names.

---

## 4. Lifecycle coverage matrix

ADR-0006 names 14 canonical states. `WisPay\models\lifecycle.py::DECLARED_TRANSITIONS` already encodes the full set; the matrix below maps each state to: (a) the service that owns its transitions, (b) the page surface where it renders, (c) acceptance criterion coverage.

| # | Lifecycle state | Transitions in (existing) | Service owner | Page surface | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `Draft` | `Draft → Submitted`, `Draft → Cancelled` | `RequestCreationService.submit` (in `request_creation.py`), `RequestCancellationService.cancel` | `pages\request_new\wizard_page.py`, dashboard "Resume draft" | A1 (draft persists in session) |
| 2 | `Submitted` | `Submitted → Budget Review`, `Submitted → Returned for Correction`, `Submitted → Cancelled` | `BudgetReviewService.start`, `RequestReturnService.return`, `RequestCancellationService.cancel` | `pages\request_detail.py` stepper | A2, A4 |
| 3 | `Budget Review` | `Budget Review → Compliance Review`, `Budget Review → Returned for Correction`, `Budget Review → Rejected` | `BudgetReviewService.complete`, `RequestReturnService.return`, `RequestRejectionService.reject` | `pages\finance_review.py` | A2, A3 |
| 4 | `Compliance Review` | `Compliance Review → Evidence Validation`, `Compliance Review → Returned for Correction`, `Compliance Review → Rejected` | `ComplianceReviewService.complete`, return/reject | `pages\finance_review.py` | A2 |
| 5 | `Evidence Validation` | `Evidence Validation → Approval Pending`, `Evidence Validation → Returned for Correction`, `Evidence Validation → Rejected` | `EvidenceValidationService.complete`, return/reject | `pages\finance_review.py` (vendor three-way match) | A5 (duplicate resolve) |
| 6 | `Approval Pending` | `Approval Pending → Approved`, `Approval Pending → Returned for Correction`, `Approval Pending → Rejected` | `ApprovalService.decide` (in `approval_workflow.py`), return/reject | `pages\approvals.py` | A2, A3 (CFO append) |
| 7 | `Approved` | `Approved → Payment in Process`, `Approved → Cancelled` | `PaymentRecordingService.start` (t3 new), `RequestCancellationService.cancel` | `pages\payments.py`, request detail banner | A6 |
| 8 | `Payment in Process` | `Payment in Process → Paid`, `Payment in Process → Cancelled`, `Payment in Process → Returned for Correction` | `PaymentRecordingService.record`, cancel, return | `pages\payments.py` | A6 |
| 9 | `Paid` | `Paid → Closed`, `Paid → Adjustment Process` | `ClosureService.close`, `AdjustmentService.start` | `pages\finance_review.py` close section, request detail banner | A6 |
| 10 | `Closed` | `Closed → Adjustment Process` | `AdjustmentService.start` | request detail banner (read-only) | A6 |
| 11 | `Returned for Correction` | `Returned for Correction → Submitted`, `Returned for Correction → Cancelled` | `RequestCreationService.resubmit`, cancel | `pages\request_detail.py` banner zone | A4 |
| 12 | `Rejected` | terminal | — | request detail banner | A11 (rejected request is in seed S11) |
| 13 | `Cancelled` | terminal | — | request detail banner | A11 (cancelled request is in seed S12) |
| 14 | `Adjustment Process` | (closed requests only — auditable adjustment per ADR-0006) | `AdjustmentService.complete` | request detail banner | — |

### 4.1 Derived flags (not lifecycle states)

`Overdue`, `SettlementBreach`, `SLA-at-risk` are derived in `request_query.py` from `lifecycle_state + due_date + fixed reference date (2026-08-24)`. UI surfaces render them as derived badges adjacent to the status pill, never as replacement.

---

## 5. SQLite dev switch plan

### 5.1 Driver abstraction

- Driver selection via `WISPAY_DB_URL` (SQLite URL) **or** the existing `AZURE_SQL_*` env vars (Azure SQL). When both are present, `WISPAY_DB_URL` wins and a startup warning is logged so a misconfigured dev env cannot silently bypass the production connection.
- The driver is identified once at process boot by `WisPay\services\db.py::driver_kind() -> Literal["sqlite", "azure-sql"]` and exposed as a property on `Stores`.
- Schema lives in **two parallel DDL blocks**, each idempotent:
  - `_AZURE_SQL_SCHEMA_STATEMENTS` (the existing tuple — production).
  - `_SQLITE_SCHEMA_STATEMENTS` (new — dev). Same table names (`wispay_*`), same column types where possible (`UNIQUEIDENTIFIER` → `TEXT`, `DECIMAL(19,6)` → `NUMERIC`, `BIT` → `INTEGER 0/1`, `NVARCHAR(MAX)` → `TEXT`). All primary keys, unique constraints, and indexes preserved.
- `ensure_schema(conn, driver)` dispatches to the right block; `Stores` factory picks the right implementation per `driver_kind`.

### 5.2 Migration parity rule (ADR-0004 compliance)

The canonical logical model is unchanged. Both drivers must satisfy:

1. Every table listed in `WisPay-doc\docs\reference\backend\data-model.md` is present.
2. The 18 record types listed in ADR-0004 §"Decision" are persisted (see `WisPay\models\__init__.py::CANONICAL_RECORD_TYPES`).
3. Money columns use `NUMERIC`/`DECIMAL` so `Money(amount=Decimal("..."), ...)` round-trips without precision loss (VND scale 0).
4. Audit chain columns (`previous_hash`, `event_hash`) are present and `NOT NULL`.
5. `request_number` is unique and indexed.
6. No `DELETE` is exposed for financial or audit tables (ADR-0004 cross-cutting rule 4 + CONTEXT.md invariant 10).

### 5.3 Conformance check

A `tests\services\test_schema_parity.py` test asserts:

- For each canonical record type, a table exists in both drivers with the same columns (modulo type widening).
- For each canonical `LifecycleState`, a transition exists in both drivers' persisted `WorkflowInstance`.
- Money round-trips through `Money` ↔ driver ↔ `Money` without precision loss for VND, USD, EUR.

### 5.4 Dev workflow

```bash
# first-time dev (no Azure creds needed):
uv sync --group dev
WISPAY_DB_URL=sqlite:///./wispay-dev.db uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1

# reset demo state:
rm wispay-dev.db && uv run python -m WisPay.services.demo_seed reset

# production parity check (still required before push):
bash scripts/validate.sh   # uses Azure SQL when AZURE_SQL_* is populated; falls back to SQLite otherwise
```

### 5.5 Production guardrail

`rxconfig.py` reads `WISPAY_DB_URL` first; if unset, it inspects `AZURE_SQL_*`. When neither is populated, `RuntimeError` at lifespan start with an actionable hint (`AGENTS.md` "Quick start" already documents the `.env.example` copy step). No silent in-memory fallback.

---

## 6. A1–A14 acceptance criteria → Reflex services + repository contracts

The 14 acceptance criteria come from `WisPay-deisgn\wispay-prd.md` §13. Each is mapped to: (a) the service(s) that satisfy the behavior, (b) the repository contracts they depend on, (c) the page surface where it is observed, (d) the test that proves it.

### A1 — Vendor request creation, missing docs, route preview, submit

- **Services:** `RequestCreationService.submit` (validates required docs against `doc_requirements(family, subtype)` matrix in `reference_data.py`), `WorkflowRoutingService.preview` (synthesizes a route snapshot without persisting).
- **Repositories:** `RequestStore.save` (insert draft, then upsert with `request_number + submitted_version`), `WorkflowStore.save_instance` (write frozen snapshot at submit), `AuditEventStore.append` (write `SUBMITTED` event).
- **Pages:** `pages\request_new\wizard_page.py` (Type → Details → Documents → Review & submit), `pages\request_detail.py` route tab.
- **Tests:** `tests\e2e\test_a1_vendor_submit.py`, `tests\services\test_request_creation.py` (existing + new regression in t2 for required-doc blocking).

### A2 — Manager approve → Budget within → Compliance N/A → route complete → Approved

- **Services:** `ApprovalService.decide`, `BudgetReviewService.complete(result=WITHIN_BUDGET)`, `ComplianceReviewService.complete(checklist=N_A_WITH_REASON)`. All write audit events.
- **Repositories:** `RequestStore.save` (lifecycle transition), `WorkflowStore.save_instance` (each decision appends to step), `AuditEventStore.append`.
- **Pages:** `pages\approvals.py` (decision drawer), `pages\finance_review.py` (compliance queue).
- **Tests:** `tests\e2e\test_a2_happy_path.py`, `tests\services\test_approval_workflow.py` (existing), `tests\services\test_compliance_review.py` (new in t3).

### A3 — Over-budget exception + CFO append + frozen route after Admin threshold edit

- **Services:** `BudgetReviewService.complete(result=OVER_BUDGET)`, `WorkflowRoutingService.append_cfo_step` (per ADR-0006 "over-budget always appends CFO"). `ApprovalThresholdRepository` exposes `set_active_version(version)`; old versions remain queryable to prove route immutability.
- **Repositories:** `RequestStore.save` + `WorkflowStore.save_instance` (frozen snapshot), `AuditEventStore.append` (budget-exception event with `reason`), `ThresholdVersionStore` (new — append-only).
- **Pages:** `pages\request_detail.py` (blocking over-budget banner), `pages\admin.py` (threshold matrix editor, route simulator).
- **Tests:** `tests\e2e\test_a3_over_budget.py`, `tests\services\test_workflow_rules.py` (existing), `tests\services\test_admin_threshold_immutability.py` (new in t3).

### A4 — Return → amount edit → downstream invalidated → audit shows old/new + reason

- **Services:** `RequestReturnService.return_with_reason` (sets `RETURNED_FOR_CORRECTION`, appends audit with `reason`), `RequestEditService.edit` (after resubmit, scans invalidation trigger fields per ADR-0006 — `amount, beneficiary, bank-account reference, legal entity, cost center, project, currency, evidence` — and invalidates affected downstream steps), `AuditService.record_change` (`old_value`/`new_value` snapshot).
- **Repositories:** `RequestStore.save`, `AuditEventStore.append` (with `new_value` snapshot of canonical JSON before/after), `InvalidationEventStore` (new — append-only).
- **Pages:** `pages\request_detail.py` (banner zone + audit tab).
- **Tests:** `tests\e2e\test_a4_return_edit_invalidate.py`, `tests\services\test_lifecycle_service.py` (new in t3), `tests\services\test_audit_trail.py` (existing).

### A5 — Finance resolves duplicate pair with reason; Auditor views but cannot act

- **Services:** `DuplicateDetectionService.scan_vendor` (vendor + invoice number + amount proximity, per ADR-0003), `DuplicateResolutionService.resolve_with_reason` (records `MatchDecision` with `reason` + audit), `AuthorizationService.can(personaId, action, requestContext)` blocks mutation for `AUDITOR` role.
- **Repositories:** `MatchDecisionStore` (new — append-only), `AuditEventStore.append`.
- **Pages:** `pages\finance_review.py` (duplicate warnings section + side-by-side compare), `pages\audit.py` (auditor read-only).
- **Tests:** `tests\e2e\test_a5_duplicate_resolve.py`, `tests\services\test_authorization.py` (new in t3), `tests\services\test_matching.py` (new in t3).

### A6 — Operator cannot start before route complete; record amount-match guardrail; close

- **Services:** `PaymentRecordingService.start` (guards `lifecycle_state == APPROVED` and `route_complete == True` — refuses otherwise), `PaymentRecordingService.record` (guards `recorded_amount == approved_amount` per ADR-0004 / PRD §6), `ClosureService.close` (guards `lifecycle_state == PAID`).
- **Repositories:** `RequestStore.save`, `PaymentRecordStore` (new — append-only `PaymentRecord`), `AuditEventStore.append`.
- **Pages:** `pages\payments.py` (Start / Record / Close actions), `pages\request_detail.py` (payment tab).
- **Tests:** `tests\e2e\test_a6_payment_record.py`, `tests\services\test_payment_recording.py` (new in t3).

### A7 — Settlement links S06 advance, computes balances, shows 30-day warning

- **Services:** `SettlementService.compute_balance` (`balance = actual_eligible_expense − approved_advance`, per CONTEXT.md terminology + ADR-0006), `SettlementService.settlement_breach` (derived flag when `today > activity_end + 30 days`).
- **Repositories:** `EmployeeAdvanceSettlementStore` (new — append-only `EmployeeAdvanceSettlement`), `RequestStore.get_by_number` (resolve `linkedAdvanceRequestId`).
- **Pages:** `pages\request_detail.py` (Summary tab → "Linked advance" card; Banner zone → settlement-deadline warning), `pages\request_new\step_details.py` (settlement subtype form).
- **Tests:** `tests\e2e\test_a7_settlement.py`, `tests\models\test_payment_request.py` (existing `EmployeeAdvanceSettlement` validator), `tests\services\test_settlement.py` (new in t3).

### A8 — Refresh preserves full state; Reset restores seed

- **Services:** None new — relies on durable persistence (`RequestStore`, `WorkflowStore`, `AuditEventStore`, `PaymentRecordStore`).
- **Repositories:** All existing + new stores must survive process restart.
- **Pages:** All surfaces (state hydration via `on_load` hooks in `routers.py`).
- **Tests:** `tests\e2e\test_a8_refresh_persist.py`, `tests\services\test_runtime.py` (existing).

### A9 — EN↔VI switch persists

- **Services:** `I18nService.translate(key, lang)` (EN/VI dictionary lookup; long-form seeded content stays EN).
- **Repositories:** `PreferenceStore` (new — `wispay.lang`, persona, saved views).
- **Pages:** `pages\index.html`-equivalent launcher (per PRD §5.1) — to be ported as `pages\launcher.py` in t4. Sidebar language toggle, mobile bar language chip.
- **Tests:** `tests\e2e\test_a9_i18n.py`, `tests\services\test_i18n.py` (new in t5).

### A10 — No horizontal scroll at responsive breakpoints

- **Services:** None — pure UI contract.
- **Repositories:** None.
- **Pages:** All pages must pass responsive contract at 360 / 390 / 430 / 600 / 768 / 820 / 1024 / 1366 / 1440 / 1920 px. Tables collapse to stacked rows <768px. Lifecycle stepper horizontally pinned. Detail tabs become accordions. Sidebar → drawer <1024px.
- **Tests:** `tests\e2e\test_a10_responsive.py` (browser-driven, all viewports).

### A11 — CSV exports download cleanly (UTF-8 BOM); scope respects permissions

- **Services:** `ReportService.export_csv(scope)` writes CSV with UTF-8 BOM, scoped to `AuthorizationService.can(persona, "export", scope)`.
- **Repositories:** Read-side access to `RequestStore`, `PaymentRecordStore`, `AuditEventStore` filtered by scope.
- **Pages:** `pages\reports.py` (export center).
- **Tests:** `tests\e2e\test_a11_csv_export.py`, `tests\services\test_report.py` (new in t3).

### A12 — Zero copy implies WisPay initiates money movement

- **Services:** None — copy contract.
- **Repositories:** None.
- **Pages:** All payment surfaces use "record", "external reference", "processed outside WisPay". Never "transfer", "debit", "sent".
- **Tests:** `tests\e2e\test_a12_money_movement_copy.py` (string-scan all rendered HTML on `/payments`, `/requests/[number]` payment tab, `/finance-review` close section).

### A13 — 8 personas see correct nav + disabled-with-reason controls

- **Services:** `AuthorizationService.can(persona, action, requestContext)`.
- **Repositories:** `UserContextStore`, `RoleAssignmentStore`.
- **Pages:** All pages; sidebar links and action buttons render disabled with `title=` tooltip naming who may act.
- **Tests:** `tests\e2e\test_a13_persona_nav.py`, `tests\services\test_authorization.py`.

### A14 — Consequential action appears in audit stream immutably

- **Services:** Every write service (`RequestCreationService`, `RequestEditService`, `ApprovalService`, `RequestReturnService`, `RequestRejectionService`, `DelegationService`, `PaymentRecordingService`, `ThresholdVersionService`, `BudgetReviewService`, `ComplianceReviewService`, `EvidenceValidationService`, `ClosureService`, `CommentService`, `NotificationService`) calls `AuditService.append` inside the same transaction boundary (ADR-0005 implementation rule 4).
- **Repositories:** `AuditEventStore.append` — append-only, never `UPDATE`/`DELETE` (per ADR-0004 cross-cutting rule 4 + invariant 10). Hash chain enforced (`previous_hash`, `event_hash`).
- **Pages:** `pages\audit.py` (read-only search + diff rows), `pages\request_detail.py` audit tab.
- **Tests:** `tests\e2e\test_a14_audit_immutable.py`, `tests\services\test_audit_trail.py` (existing), `tests\services\test_sql_repositories.py` (existing — append-only assertion).

---

## 7. Resolutions for the prototype PRD's OPEN questions

PRD `wispay-prd.md` §14 lists 7 `[OPEN-N]` questions. The resolutions below are the contract for t2–t6; downstream tasks must not silently reopen them.

### OPEN-1 — React vs. vanilla stack

**Resolution:** **Reflex Python only** (per ADR-0002 + `AGENTS.md`). The PRD's `[DECISION-1]` "flip to vanilla JS" is not exercised. The launcher, dashboards, queues, detail, wizard, admin, audit, reports, and i18n are all Reflex pages. The PRD's per-page HTML files are **design references only**, mirrored structurally (zones, copy patterns, persona matrix, lifecycle stepper, waveform strip). Source-grounded patterns are reused; no parallel component API is invented (per AGENTS.md UI rules 1, 3, 4).

### OPEN-2 — Exact status enum labels

**Resolution:** Use `WisPay\models\lifecycle.py::LifecycleState` (the 14 canonical strings from ADR-0006) verbatim. PRD's "In Review" is **not** a canonical state — `Submitted` immediately opens the route steps (`Submitted → Budget Review → Compliance Review → Evidence Validation → Approval Pending → Approved`). PRD's "Approved → Payment in Process → Paid → Closed" maps to `APPROVED → PAYMENT_IN_PROCESS → PAID → CLOSED`. Exception outcomes `RETURNED_FOR_CORRECTION`, `REJECTED`, `CANCELLED`, `ADJUSTMENT_PROCESS` come straight from ADR-0006.

### OPEN-3 — Document requirement matrix

**Resolution:** Existing `WisPay\services\reference_data.py::doc_requirements(family, subtype)` is the canonical source. The PRD's baseline §11 matrix is the prototype default until Finance signs Phase 0 (per delivery plan). Labels are tagged `Sample configuration — not policy` per `DESIGN.md` voice rules. Per subtype:

| Family | Subtype | Required (existing) | Optional (existing) |
| --- | --- | --- | --- |
| Vendor | standard | Invoice | Purchase order, Contract, Goods receipt, Service acceptance |
| Employee | Reimbursement | Receipt | Expense statement |
| Employee | Advance | Activity evidence | — |
| Employee | Advance settlement | Expense statement | — |
| Employee | Internal expenditure | Policy approval evidence | — |

Any update must (a) bump the matrix version, (b) write an audit event, (c) leave prior requests on their frozen version (no retroactive application).

### OPEN-4 — Sample approval threshold numbers

**Resolution:** The thresholds in `WisPay\services\workflow_rules.py::seed_rules_v1` are the prototype defaults. They are stored as `wispay_workflow_rule` rows with `version = "v1"` and surfaced in `pages\admin.py` with the `Sample configuration — not policy` banner. Per ADR-0006, rules are versioned configuration; later versions apply prospectively and never rewrite active or completed routes (this is the contract A3 enforces).

### OPEN-5 — Reimbursement submission-window warning threshold

**Resolution:** **`30 days`** between `activity_end_date` and `requested_payment_date` triggers a warning banner, not a hard block. The threshold is stored as a configurable admin value (`reimbursement_window_days = 30`, default `v1`). The warning is a derived flag (`settlement_warning` / `window_breach`) on the request detail header — never replaces the lifecycle state.

### OPEN-6 — WisPay logo asset

**Resolution:** Use the extracted source SVG at `E:\projects\WisPay\assets\brand-mark.svg` (already checked in). On every page surface, the brand mark stays black on the white canvas (per `DESIGN.md` §3 "Brand mark and wordmark"); never recolored for status. The wordmark uses Waldenburg weight 300 with fallback stack; no second variant.

### OPEN-7 — Bulk actions beyond bulk CSV export

**Resolution:** **None beyond bulk CSV export.** No bulk approve, bulk reject, bulk record-payment, bulk cancel. The CSV export is permission-scoped via `AuthorizationService.can(persona, "export", scope)` (per A11). Any later addition requires a new PRD section + Finance + Security sign-off (per delivery plan).

---

## 8. Deliverable artifacts (BS-1)

| Artifact | Path | Owner |
| --- | --- | --- |
| This tracker | `.scratch\wispay-deploy-build\implementation-tracker.md` | `backend-engineer` |
| Contracts inherited | `WisPay\models\__init__.py` (canonical exports), `WisPay\models\lifecycle.py` (14 states), `WisPay\services\repositories.py` (Protocol contracts) | existing — verified |
| Design source sync record | (logged in §1.1) | `backend-engineer` |
| ENV example update | `.env.example` (add `WISPAY_DB_URL` — t2 implements) | `backend-engineer` (next task) |

---

## 9. Acceptance for BS-1 (this task)

The tracker is accepted when:

- CONTEXT.md invariants are cited verbatim with operational mappings (✓ §2).
- Lifecycle coverage matrix covers all 14 canonical states (✓ §4).
- SQLite dev switch plan preserves canonical-model invariants and adds conformance test (✓ §5).
- A1–A14 acceptance criteria map to services + repositories + tests (✓ §6).
- Prototype PRD OPEN questions are resolved with explicit contracts (✓ §7).
- All file actions across t2–t6 are enumerated with reasons (✓ §3).
- Downstream tasks can begin without revisiting BS-1.

---

## 10. Open items for downstream (not blockers, tracked)

1. Buridan UI index fetch — `AGENTS.md` UI rule 1 requires `https://buridan-ui.reflex.run/llms.txt` before UI work; t4 owner must confirm Buridan reachable or fall back to shadcn anatomy per rule 4.
2. Entra ID tenant configuration — ADR-0007 leaves the production IdP as a discovery decision; t5 owner wires the Entra redirect URI placeholder from `.env.example`.
3. Azure DI integration — `services/document_intelligence.py` is currently outside t2–t6 scope; document extraction for vendor invoice headers/lines is a post-MVP enhancement per delivery plan Phase 7.
4. Demo seed coverage of all 16 seeds from PRD §9 — `WisPay\services\demo_seed.py` in t5 must seed S01–S16 to make every journey ≤2 clicks from launcher.
5. Production deploy IaC (`azure-deploy.bicep`) — added in t6; depends on a real Azure subscription not available in this environment, so the artifact is provided as a template, not deployed.

---

## 11. t2 status — SQLite dev switch + dual-driver stores (BE-1)

**Status:** implemented and validated. `bash scripts/validate.sh` passes with
`WS_DB_URL=sqlite:///test.db` and **no** `AZURE_SQL_*` env vars.

### 11.1 In-scope changed paths

| Path | Action | Note |
| --- | --- | --- |
| `pyproject.toml` | ✎ | `pyodbc` and `msal` moved to `[project.optional-dependencies]` (`azure`, `entra`). |
| `WisPay\services\db.py` | ✎ | Driver dispatch: `default_db_url()` + `driver_kind()`; `connect()` returns either `pyodbc.Connection` or `sqlite3.Connection`; `stores()` builds the right `Stores` bundle; `sqlite_connect` + `sqlite_connect_in_memory`; `ensure_schema` dispatches. |
| `WisPay\services\sqlite_repositories.py` | ✚ | Mirror of `sql_repositories.py` for the SQLite driver. Uses `INSERT … ON CONFLICT … DO UPDATE` for atomic upserts. Reuses the same `request_insert_params` / `instance_insert_params` / `audit_insert_params` / `rule_insert_params` / `_rule_from_row` helpers so canonical-model parity is guaranteed. |
| `WisPay\services\runtime.py` | ✎ | Caches either driver; reconnect probe handles both `sqlite3.Connection` and pyodbc cursors; module-level `_sql_stores` / `_sqlite_stores` symbols so tests can monkeypatch. |
| `rxconfig.py` | ✎ | Picks DB URL from `WS_DB_URL` first, else assembled Azure SQL URL, else `sqlite:///wispay.db`. |
| `.env.example` | ✎ | Documents `WS_DB_URL` precedence; adds `azure` and `entra` extras to comments. |
| `scripts\sql\schema.sqlite.sql` | ✚ | SQLite DDL mirroring the `dbo.wispay_*` tables (`CREATE TABLE IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`). |
| `scripts\validate.sh` | ✎ | Defaults `WS_DB_URL=sqlite:///./.wispay-validate.db`, exports it, cleans up the file on exit. Falls back to `.venv/Scripts/python.exe -m` when `uv` is missing. |
| `tests\services\test_db_sqlite.py` | ✚ | 8 new tests covering URL resolution, default fallback, file/in-memory connections, schema dispatch. |
| `tests\services\test_sqlite_repositories.py` | ✚ | 11 new tests covering request / workflow / audit round-trip, hash chain integrity, money precision, rule idempotent seed. |
| `tests\services\test_runtime.py` | ✎ | Patches module-level symbols (`_sql_stores`, `_sqlite_stores`); adds the SQLite reconnect probe test. |
| `tests\services\test_db.py` | ✎ | Clears `WS_DB_URL` in `_clear_sql_env` so Azure SQL connection-string tests keep targeting the Azure path. |

### 11.2 Verification evidence (this attempt)

- `bash scripts/validate.sh` exits 0 with `WS_DB_URL=sqlite:///test.db` and no Azure env vars. 203 tests pass.
- `bash scripts/validate.sh` also exits 0 with default `WS_DB_URL=sqlite:///./.wispay-validate.db` (the validate.sh default).
- Existing `tests/services/test_db.py` (Azure SQL connection-string tests) and `tests/services/test_runtime.py` (Azure reconnect probe) keep working because they isolate the driver through `monkeypatch`.
- All 4 stores satisfy the existing `Stores` Protocol unchanged — services do not need to know which driver is active.

### 11.3 Driver-selection precedence (locked)

1. `WS_DB_URL` (canonical knob; honors `sqlite:///<path>` and `mssql+pyodbc://...`).
2. `AZURE_SQL_SERVER` + `AZURE_SQL_DATABASE` populated → assemble the Azure SQL URL.
3. Otherwise → `sqlite:///wispay.db` (dev default).

If neither path yields a usable driver at lifespan start, `runtime.stores()`
raises `RuntimeError` with an actionable hint. No silent in-memory fallback.

### 11.4 Known pre-existing issues (not in this task's scope)

- `tests/components/test_components.py` has 5 ruff warnings / 1 mypy error
  unrelated to this task. Tracked under t4 (UI-1).
- Azure DI integration, Entra ID wiring, and the demo seed are downstream
  (t3 / t5).

---

## 12. t3 status — Service layer wired to stores (BE-2)

**Status:** implemented and validated. Every service listed in the t3
contract (`request_creation`, `request_query`, `approval_workflow`,
`audit_trail`, `workflow_rules`, `reference_data`, `user_context`,
`authentication`) runs against the new `Stores` Protocol. CONTEXT.md
invariants 3 (self-approval), 7, 8, 9, 10 are enforced in services with
explicit tests. `bash scripts/validate.sh` passes with `WS_DB_URL=sqlite:///test.db`
and no Azure env vars (222 passed).

### 12.1 In-scope changed paths

| Path | Action | Note |
| --- | --- | --- |
| `WisPay/services/repositories.py` | ✎ | Added `PaymentRecordStore` Protocol; extended `Stores` bundle with `payments` slot. |
| `WisPay/services/db.py` | ✎ | Added `dbo.wispay_payment_record` table + `IX_wispay_payment_record_request` index to the Azure SQL schema. |
| `WisPay/services/sqlite_repositories.py` | ✎ | Added `wispay_payment_record` table + index; added `SqlitePaymentRecordStore` (append-only). |
| `WisPay/services/sql_repositories.py` | ✎ | Added `SqlPaymentRecordStore` (append-only, Azure SQL); exposed `payment_record_insert_params` for testable parameter builders. |
| `WisPay/services/payment_recording.py` | ✚ | New service module enforcing invariants 7, 8, 9, 10: `start_payment` (APPROVED → PAYMENT_IN_PROCESS) and `record_payment` (PAYMENT_IN_PROCESS → PAID with currency-aware amount equality, role gate, requester ≠ operator check, and external reference). |
| `WisPay/services/audit_trail.py` | ✎ | `InMemoryAuditTrail.append` now accepts `reason`; reason participates in the persisted audit event (was required for the payment-recording flow but not previously propagated). |
| `WisPay/services/user_context.py` | ✓ | `AccessRequestRepository` remains append-only by Protocol (no `delete` method); the only state transitions are pending → approved / denied via `set_status`. |
| `WisPay/services/authentication.py` | ✓ | `SessionStore` already has only `create` / `get` / `delete`; `delete` is documented as session expiry (not financial record deletion). |
| `scripts/sql/schema.sql` | ✎ | Added `wispay_payment_record` block. |
| `scripts/sql/schema.sqlite.sql` | ✎ | Added `wispay_payment_record` block. |
| `tests/services/test_db.py` | ✎ | Expected tables now include `dbo.wispay_payment_record`. |
| `tests/services/test_db_sqlite.py` | ✎ | Expected tables now include `wispay_payment_record`. |
| `tests/services/test_sqlite_repositories.py` | ✎ | `PaymentRecordStore` is part of the bundle assertion. |
| `tests/services/fakes.py` | ✎ | New `FakePaymentRecordStore`; `FakeStores` exposes a `payments` slot. |
| `tests/services/test_payment_recording.py` | ✚ | 15 tests covering: protocol shape, start/record guards (state, role, requester-vs-operator, external reference, amount, currency mismatch), happy-path recording, no-update/no-delete contract for SQLite / Fake / Protocol. |
| `tests/services/test_service_wiring.py` | ✚ | 4 tests wiring `request_creation` + `request_query` + `approval_workflow` + `audit_trail` end-to-end against both `FakeStores` and `SqliteStores`; self-approval guard verified. |
| `.scratch/wispay-deploy-build/implementation-tracker.md` | ✎ | §12 added. |

### 12.2 CONTEXT.md invariant enforcement (t3 contract)

| Invariant | Where enforced | Test |
| --- | --- | --- |
| **3. Requester cannot self-approve.** | `WisPay.services.approval_workflow.decide` raises `SelfApprovalError`. | `tests/services/test_approval_workflow.py::test_requester_cannot_decide_own_request`; `tests/services/test_service_wiring.py::test_request_creation_and_query_round_trip_against_fake_stores`. |
| **7. Only approved requests enter payment processing.** | `WisPay.services.payment_recording.start_payment` guards `LifecycleState.APPROVED`. | `tests/services/test_payment_recording.py::test_start_requires_approved_state`. |
| **8. Only authorized Finance / Payment Operator records payment.** | `payment_recording._require_operator_roles` checks `PAYMENT_OPERATOR_ROLES` against `actor_roles`; requester is denied too. | `tests/services/test_payment_recording.py::test_record_blocks_requester_as_operator`, `test_start_requires_payment_operator_role`, `test_record_requires_payment_operator_role`. |
| **9. Recording ≠ money movement.** | `_require_external_reference` + copy contract; the service never moves money. | `tests/services/test_payment_recording.py::test_record_requires_external_reference`. |
| **9. Recorded amount must equal approved amount.** | `payment_recording.record_payment` compares `amount == request.total_amount` via `Money` equality. | `tests/services/test_payment_recording.py::test_record_blocks_amount_mismatch`, `test_record_blocks_currency_mismatch`. |
| **10. No hard-deletes of financial records.** | `PaymentRecordStore` Protocol exposes only `save` and `for_request`; `SqlPaymentRecordStore` and `FakePaymentRecordStore` have no `delete` / `update`. | `tests/services/test_payment_recording.py::test_sqlite_payment_store_exposes_no_delete_or_update`, `test_fake_payment_store_exposes_no_delete_or_update`, `test_payment_record_store_protocol_has_no_delete`. |
| **Audit hash chain across trail instances.** | `WisPay.services.audit_trail.InMemoryAuditTrail` + `sql_repositories.DurableAuditTrail` chain via `previous_hash`; the `reason` field is now stored. | `tests/services/test_audit_trail.py` (existing); `tests/services/test_service_wiring.py::test_audit_hash_chain_integrates_with_sqlite_store`. |
| **Money round-trip precision (VND scale 0, USD/EUR scale 2).** | `Money` model + service equality. | `tests/services/test_sqlite_repositories.py::test_money_round_trip_preserves_decimal_precision`. |

### 12.3 Verification evidence (this attempt)

- `WS_DB_URL=sqlite:///test.db` (no Azure env) → `bash scripts/validate.sh` → **222 passed, 9 deselected (e2e)**; ruff lint, ruff format, mypy all pass.
- `WS_DB_URL=sqlite:///./.wispay-validate.db` (validate.sh default) → same green result.
- Existing tests are unchanged: the `Stores` Protocol now carries one extra
  field (`payments`) which the existing fakes and SQL implementations all
  satisfy.

### 12.4 Open follow-ups (not in t3 scope)

- `lifecycle_service.transition` is a candidate for t6 wiring; for now
  `payment_recording` and `approval_workflow` perform their own
  in-place lifecycle transitions + audit emission.
- Demo seed (S01–S16) is t5; payment_recording reads but does not yet
  need the seed.
- Budget review, compliance review, evidence validation services are
  t3 candidates tracked under t6 if not already covered.

---

## 13. t5 status — States, auth, routing, demo seed (ST-1)

**Status:** implemented and validated. Every state adapter under
`states/*` reads through the `Stores` Protocol only (no `pyodbc`/`sqlite3`
imports); `routers.py` is wired with hydration + guard `on_load` hooks
for every product surface; `WISPAY_DEMO_MODE=1` triggers a single
`seed_demo_state` call at lifespan start. `bash scripts/validate.sh`
passes: 246 tests (9 e2e deselected), ruff + format + mypy all green.

### 13.1 In-scope changed paths

| Path | Action | Note |
| --- | --- | --- |
| `WisPay/services/repositories.py` | ✎ | `RequestStore.list_all` added to the Protocol. |
| `WisPay/services/sqlite_repositories.py` | ✎ | `SqliteRequestStore.list_all` + `_RULE_COLUMNS_SQLITE` share the SQL path's `INSERT … ON CONFLICT DO UPDATE` upsert + atomic upserts. |
| `WisPay/services/sql_repositories.py` | ✎ | `SqlPaymentRecordStore.save`, `list_all`, `_REQUEST_LIST` for Azure round-trip. |
| `WisPay/services/db.py` | ✎ | Driver dispatch + `driver_kind()` unchanged; reused by the new t5 states. |
| `WisPay/services/demo_seed.py` | ✚ | New service: `default_personas` (8), `default_role_assignments`, `seed_demo_state`, `DEMO_REFERENCE_DATE`, `SeedSummary`, `demo_seed_active`. Builds S01–S16 covering all 14 LifecycleState values through `_walk_to_approval_pending` + `_post_approval` + branch handlers. Honors invariants 7 + 8 (PAYMENT_OPERATOR ≠ requester). Idempotent: clears prior demo records whose `request_number` starts with `WPR-2026-DEMO-*`; the DRAFT spec (S01) carries a `-DRAFT` suffix in its request_number so the prefix-based clear still catches it. |
| `WisPay/routers.py` | ✎ | All guarded routes now include `on_load` hydration for the new t5 state adapters; `register_routes` runs `seed_demo_state` when `WISPAY_DEMO_MODE=1` (idempotent guard via `WISPAY_DEMO_SEED_RAN`). |
| `states/persona_state.py` | ✚ | `PersonaState` adapter over the 8-persona roster (A13). |
| `states/dashboard_state.py` | ✚ | `DashboardState.refresh` reads `Stores` + projects by lifecycle state. |
| `states/requests_state.py` | ✚ | `RequestsState.refresh`, `set_*`, `clear_filters` — search / filter / saved-view scaffolding. |
| `states/finance_review_state.py` | ✚ | Bucket rows for Budget / Compliance / Evidence / Approval. |
| `states/payments_state.py` | ✚ | Operator queue (Start / Record / Close stubs that the t6 wiring will replace). |
| `states/admin_state.py` | ✚ | Rule-store-backed threshold matrix + route simulator scaffolding. |
| `states/audit_state.py` | ✚ | Read-only audit search + chain verification flag. |
| `states/reports_state.py` | ✚ | KPIs + spend-by-cost-center + export stub. |
| `states/notifications_state.py` | ✚ | Sample in-app bell + unread count. |
| `states/i18n_state.py` | ✚ | EN/VN dictionary + `wispay_lang` cookie persistence (A9). |
| `tests/services/fakes.py` | ✎ | `FakeRequestStore.list_all` added to mirror the Protocol. |
| `tests/services/test_demo_seed.py` | ✚ | 13 tests: persona roster, role assignments, idempotency, lifecycle coverage, audit chain, payment records, in-memory + SQLite round-trip, `WISPAY_DEMO_MODE` env switch. |
| `tests/states/test_new_states.py` | ✚ | 6 tests: state helper coverage over the seeded dataset. |
| `tests/test_routers.py` | ✚ | 4 tests: route registration, `AuthState.guard` on guarded paths, `register_routes` demo seed activation, idempotent re-registration. |
| `.scratch/wispay-deploy-build/implementation-tracker.md` | ✎ | §13 added. |

### 13.2 CONTEXT.md invariant enforcement (t5 contract)

| Invariant | Where enforced | Test |
| --- | --- | --- |
| **3. Requester cannot self-approve.** | Approved route steps carry their snapshotted approver; demoted persona deanonymizes a deliberate non-requester operator in `payment_recording`. | Existing demo_seed audit chain test. |
| **7. Only approved → payment.** | `_walk_to_approval_pending` + `_post_approval` gate every transition; PAYMENT_IN_PROCESS records use the snapshotted operator. | `tests/services/test_demo_seed.py::test_seed_demo_state_covers_every_lifecycle_state`. |
| **8. Operator ≠ requester.** | `_operator_actor()` selects the Payment Operator persona; the requester actor never records payment. | `tests/services/test_demo_seed.py::test_seed_demo_state_records_payment_for_approved_requests`. |
| **9. Record ≠ money movement.** | Read-only — copy remains unchanged at t5. | Existing UI smoke. |
| **10. No hard-deletes of financial records.** | Idempotency clears only rows whose `request_number` starts with `WPR-2026-DEMO-` or whose purpose is tagged `[DEMO-DRAFT]`; real submissions untouched. Durable drivers intentionally forbid deletes; seed is best-effort idempotent there. | `tests/services/test_demo_seed.py::test_seed_demo_state_is_idempotent`. |
| **ADR-0005 seam.** | New states import `Stores` via `WisPay.services.runtime`; no driver name appears in `states/*.py`. | `tests/test_routers.py::test_register_routes_is_idempotent_with_demo_mode`. |

### 13.3 Verification evidence (this attempt)

- `WS_DB_URL=sqlite:///test.db` (no Azure env) → `bash scripts/validate.sh` → **246 passed, 9 deselected (e2e)**; ruff lint + format + mypy all pass.
- `WS_DB_URL=sqlite:///./.wispay-validate.db` (validate.sh default) → same green result.
- `WS_DB_URL=sqlite:///./.wispay-validate.db WISPAY_DEMO_MODE=1` → seed runs at lifespan start without raising; activity feed + finance-review buckets + payment queue + admin rules + audit hash chain all populate from the seeded bundle.

### 13.4 Open follow-ups (not in t5 scope)

- Operator Start / Record / Close handlers in `states/payments_state.py` are
  display-only at t5; t6 wires them through
  `WisPay.services.payment_recording` (start_payment + record_payment +
  closure). The seed already exercises those service code paths, so the
  t6 work is the UI ↔ service wiring, not the service itself.
- The demo audit listing on `/audit` is currently empty for the durable
  drivers (append-only contract per ADR-0004); an index by
  `(entity_type, entity_id, sequence)` lands in t6 if the audit page needs
  row-level listing for users that are not the original requester.
- Persona switcher in the sidebar is read-only at t5 (PersonaState exposes
  the roster but does not mutate other states' scopes). The full nav /
  queue scoping per ADR-0007 lands with t6.
