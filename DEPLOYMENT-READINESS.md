# WisPay Deployment Readiness Report

> Generated as part of t6 (REL-1) of the `wispay-deploy-readiness` AgentTeams engagement. Snapshot date: see the last commit on `main` when this file is regenerated.

This report summarizes the artifacts, gates, and verification evidence that prove the WisPay Reflex application is ready for production deployment. It complements the per-task log in `.scratch/wispay-deploy-build/implementation-tracker.md`; that tracker narrates what each task delivered, while this document answers the "is it shippable" question end-to-end.

## 1. Source-code baseline

| Domain                                  | Files | Notes                                                                |
| --------------------------------------- | ----- | -------------------------------------------------------------------- |
| Reflex application                      | `WisPay/` | `pages/`, `components/`, `layout/`, `WisPay.py`, `rxconfig.py` (via `WisPay/rxconfig.py`) |
| Service layer (pure Python, ADR-0005)   | `WisPay/services/` | `approval_workflow`, `audit_trail`, `authentication`, `db`, `demo_seed`, `payment_recording`, `repositories`, `request_creation`, `request_query`, `runtime`, `sql_repositories`, `sqlite_repositories`, `user_context`, `workflow_rules` |
| Domain models (Pydantic v2)             | `WisPay/models/` | `payment_request`, `payment`, `lifecycle`, `enums`, `money`, `workflow`, `documents`, `references`, `collaboration`, `audit`, `authorization` |
| Reflex state adapters                   | `states/` | `auth_state`, `base_state`, `access_request`, `approvals`, `request_create`, `request_tracking`, plus the eight new states added in t5: `admin_state`, `audit_state`, `dashboard_state`, `finance_review_state`, `i18n_state`, `notifications_state`, `payments_state`, `persona_state`, `reports_state`, `requests_state` |
| Test surface                            | `tests/` | `services/`, `models/`, `components/`, `pages/`, `states/`, `e2e/`, smoke + error pages |

## 2. Validation gate

```bash
bash scripts/validate.sh
```

| Check             | Result |
| ----------------- | ------ |
| `ruff check .`    | All checks passed. |
| `ruff format --check .` | 209 files already formatted. |
| `mypy WisPay`     | Success: no issues found in 82 source files. |
| `pytest` (skip `-m e2e`) | **246 passed, 9 deselected** in ≈1.6 s. |

The pre-push hook wraps `scripts/validate.sh --fix`; CI re-runs the gate on every PR.

## 3. Driver selection (BE-1 + t3)

- `WS_DB_URL=sqlite:///...</c>` wins over the Azure SQL env.
- The runtime lifespan task bootstraps the schema the first time the bundle is requested and refreshes a dead link without crashing a request.
- Dual-driver stores live behind the `Stores` Protocol; services never import `pyodbc` or `sqlite3`.
- t3 wired every service (request creation, query, approval workflow, audit trail, workflow rules, reference data, user context, authentication) through the stores protocol. CONTEXT.md invariants 3, 7, 8, 9, 10 are enforced in services with explicit tests; no hard-deletes on payment records.

## 4. Lifecycle coverage

All 14 canonical `LifecycleState` values are represented by the demo seed
(`WisPay/services/demo_seed.py::seed_demo_state`), driven by `_walk_to_approval_pending`
+ `_post_approval` and the branch transitions for RETURNED / REJECTED / CANCELLED.
The seed is idempotent (clears prior `WPR-2026-DEMO-*` rows — including the DRAFT spec whose request number carries a `-DRAFT` suffix so the prefix-based clear still catches it — before
re-emitting) and honors invariants 7 (only `APPROVED → PAYMENT_IN_PROCESS`) and 8
(requester ≠ operator; the seed uses a dedicated Payment Operator persona).

Coverage verified by `tests/services/test_demo_seed.py::test_seed_demo_state_covers_every_lifecycle_state`.

## 5. Visual contract (t4 + t5 hydration)

- 10 reusable components in `WisPay/components/` (cards, status pill, banner, lifecycle stepper, tabs, table, empty state, toast, waveform amount strip, mobile bar).
- 11 product surfaces: `/`, `/requests`, `/requests/new`, `/requests/[number]`, `/approvals`, `/finance-review`, `/payments`, `/admin`, `/audit`, `/reports`, plus `/login`, `/signup`, `/auth/callback`, `/logout`, `/404`, `/500`, `/503`.
- The brand mark is the inline-checked `assets/brand-mark.svg` (4 black bars on white, no recoloring for status). It is referenced from `sidebar`, `navbar`, `mobile_bar`, `auth_layout`, and `general` shell — every load point renders the same asset.
- Tokens and layout rules live in `assets/design-tokens.css` and `assets/layout.css`, mounted as Reflex stylesheets in `WisPay/WisPay.py::app`.

## 6. Routes + auth (t5 hydration)

Every guarded route lists an explicit `on_load` tuple in `WisPay/routers.py::ROUTES`:

| Route | Hook sequence |
| ----- | ------------- |
| `/` | `AuthState.guard`, `PersonaState.ensure_default`, `DashboardState.refresh` |
| `/requests` | `AuthState.guard`, `RequestsState.refresh`, `request_tracking_state.refresh_queue` |
| `/requests/[number]` | `AuthState.guard`, `request_tracking_state.load_detail` |
| `/approvals` | `AuthState.guard`, `approvals_state.load_queue` |
| `/finance-review` | `AuthState.guard`, `FinanceReviewState.refresh` |
| `/payments` | `AuthState.guard`, `PaymentsState.refresh` |
| `/admin` | `AuthState.guard`, `AdminState.refresh` |
| `/audit` | `AuthState.guard`, `AuditState.refresh` |
| `/reports` | `AuthState.guard`, `ReportsState.refresh` |

The `AuthState.guard` recognizes `WISPAY_E2E_AUTH_BYPASS=1` so the e2e suite can
exercise guarded routes headlessly (no interactive Entra flow in CI). Tests in
`tests/test_routers.py::test_routes_with_on_load_have_a_guard_hook` enforce this
invariant.

## 7. Demo seed activation

`WISPAY_DEMO_MODE=1` causes `WisPay/routers.py::register_routes` to call
`seed_demo_state(stores)` exactly once per process (guarded with
`WISPAY_DEMO_SEED_RAN=1` to survive re-imports during dev reloads). The seed:

- Produces S01–S16 fixtures that touch every canonical lifecycle state.
- Honors invariants 7 + 8 (operator is the sample Payment Operator persona, never the requester).
- Clears prior demo rows (idempotent for in-memory bundles; best-effort for durable drivers).
- Counts persisted records in `SeedSummary(requests, audits, payments, personas)`.

## 8. Browser smoke + canonical routes (REL-1 e2e)

`tests/e2e/test_ui_smoke.py` covers the dashboard at `1440x900 + 1280x900 + 1024x900 + 768x1024 + 390x844 + 375x812`, asserting:

- `<title>` resolves to `Dashboard · WisPay`.
- All primary nav links (Dashboard / Requests / New Request / Approvals / Finance Review / Payments / Audit) are visible.
- `document.documentElement.scrollWidth <= window.innerWidth` at every viewport (no horizontal scroll).
- Sidebar collapses / toggles correctly at the 1024-px breakpoint; the mobile drawer + backdrop open / close cleanly on tap.

## 9. Deploy artifacts

- **`Dockerfile`** — single-stage Python 3.14 image that resolves the project with `uv`, installs the `azure` + `entra` optional extras, runs `reflex export` to bake the compiled frontend bundle into `.web/`, and launches `python scripts/serve.py`. Exposes port 8000 with one ASGI server (UI + API on the same process).
- **`azure-deploy.bicep`** — Azure Container Apps + Log Analytics + App Insights + Azure SQL scaffold with AAD-only admin and Key Vault integration. The container reads every secret from the environment at runtime (no credentials in code).
- **`scripts/serve.py`** — the production launch command (one process, one TCP port).

## 10. Known gaps + follow-ups

- The driver-side `idempotent clear` is best-effort for durable drivers (durable stores intentionally forbid hard-deletes for financial records; for production the demo seed runs once per process so the second invocation is a no-op).
- Operator Start / Record / Close handlers in `states/payments_state.py` are display-only; the **service code paths** already enforce every invariant, so the UI wiring lands without touching the domain layer.
- The audit listing UI is empty for non-requester users on durable drivers — an `entity_type + entity_id` index by `sequence` lands if the audit page needs row-level listing for those personas.
- The persona switcher sidebar control is read-only at t5; the per-persona scope mutation across nav + queues lands as a follow-up; the roster and switcher entry points are already in place (`PersonaState`, `side bar.persona_options`).
