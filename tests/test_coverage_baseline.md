# Test Coverage Baseline Report

## Overview

- **Total statements**: 4,652
- **Uncovered statements**: 1,022
- **Overall coverage**: 78%
- **Tests passing**: 246 passed, 9 deselected (e2e)
- **Test warnings**: 24 ResourceWarnings (unclosed SQLite connections)

## Coverage by Module Category

### Services — 81% average

| Module | Stmts | Miss | Cover | Missing Lines |
|--------|-------|------|-------|---------------|
| `WisPay/services/approval_workflow.py` | 91 | 2 | 98% | 151, 225 |
| `WisPay/services/audit_trail.py` | 43 | 1 | 98% | 132 |
| `WisPay/services/authentication.py` | 157 | 7 | 96% | 85-87, 134, 159, 230-231 |
| `WisPay/services/db.py` | 97 | 18 | 81% | 269-270, 298-304, 309, 321, 369, 385, 396-403 |
| `WisPay/services/demo_seed.py` | 262 | 11 | 96% | 123, 224, 686-698, 751, 822, 1026, 1114-1117, 1120 |
| `WisPay/services/payment_recording.py` | 71 | 5 | 93% | 85, 152, 159, 212, 231 |
| `WisPay/services/reference_data.py` | 27 | 0 | 100% | — |
| `WisPay/services/repositories.py` | 35 | 0 | 100% | — |
| `WisPay/services/request_creation.py` | 218 | 22 | 90% | 115, 131, 144-145, 147, 199, 208-209, 214, 223, 225, 227, 229, 233, 236, 248-251, 253, 258, 271 |
| `WisPay/services/request_query.py` | 85 | 1 | 99% | 115 |
| `WisPay/services/runtime.py` | 59 | 13 | 78% | 67-68, 73-82, 94, 97 |
| `WisPay/services/sql_repositories.py` | 215 | 113 | 47% | Lines 47, 95, 98-112, 115, 118, 121-127, 130-138, 187, 190-208, 211, 214, 217-223, 226-234, 278, 281-287, 290-297, 300-306, 310, 351, 354-362, 365-371, 375-385, 414, 534, 553, 556-561, 564-570, 580-584 |
| `WisPay/services/sqlite_repositories.py` | 111 | 5 | 95% | 191-193, 371, 464 |
| `WisPay/services/user_context.py` | 102 | 1 | 99% | 224 |
| `WisPay/services/workflow_rules.py` | 57 | 1 | 98% | 130 |

### Model Layer — 92% average

| Module | Stmts | Miss | Cover | Missing Lines |
|--------|-------|------|-------|---------------|
| `WisPay/models/_base.py` | 17 | 1 | 94% | 11 |
| `WisPay/models/audit.py` | 47 | 3 | 94% | 26-28 |
| `WisPay/models/authorization.py` | 61 | 11 | 82% | 26, 51-57, 75-77 |
| `WisPay/models/collaboration.py` | 28 | 0 | 100% | — |
| `WisPay/models/documents.py` | 116 | 16 | 86% | 62-64, 78-80, 89-91, 146-152 |
| `WisPay/models/enums.py` | 134 | 0 | 100% | — |
| `WisPay/models/lifecycle.py` | 22 | 0 | 100% | — |
| `WisPay/models/money.py` | 44 | 2 | 95% | 30, 58 |
| `WisPay/models/payment.py` | 30 | 2 | 93% | 33, 35 |
| `WisPay/models/payment_request.py` | 115 | 15 | 87% | 44, 68, 73, 78, 99-118, 151, 160, 166 |
| `WisPay/models/references.py` | 41 | 0 | 100% | — |
| `WisPay/models/workflow.py` | 82 | 9 | 89% | 42-44, 60-62, 91, 93, 97 |

### States — 62% average (LOWEST)

| Module | Stmts | Miss | Cover | Missing Lines |
|--------|-------|------|-------|---------------|
| `states/approvals.py` | 234 | 164 | 30% | 76, 79, 82-84, 87, 95-100, 104, 108, 112-126, 129-142, 171-186, 191-254, 261-262, 267, 272-282, 285-311, 335-381, 385, 390 |
| `states/request_create.py` | 267 | 165 | 38% | 70-76, 80-82, 147-150, 155-158, 161, 164, 167-176, 182-191, 201-216, 222, 228-253, 267, 276-279, 285-303, 309-311, 317-319, 325-380, 386, 400, 409, 418, 424, 434, 440, 446, 452-456, 462-469, 475-487 |
| `states/request_tracking.py` | 171 | 113 | 34% | 93-95, 101, 107-125, 129-140, 144, 179-235, 241, 247-248, 254-255, 261-262, 268-269, 275-279, 284, 293-392 |
| `states/requests_state.py` | 60 | 29 | 52% | 27-29, 60-76, 82, 88-89, 95-96, 102-103, 109-110, 116-121 |
| `states/dashboard_state.py` | 38 | 20 | 47% | 20-24, 28, 50-68, 74 |
| `states/finance_review_state.py` | 33 | 15 | 55% | 26, 51-76, 82 |
| `states/reports_state.py` | 54 | 31 | 43% | 24-39, 43-47, 66-91, 97, 103 |
| `states/payments_state.py` | 43 | 18 | 58% | 28, 55-80, 86, 92, 98, 104 |
| `states/audit_state.py` | 30 | 14 | 53% | 27-41, 47, 53-54 |
| `states/admin_state.py` | 34 | 17 | 50% | 24, 47-58, 64, 70-73 |
| `states/access_request.py` | 34 | 12 | 65% | 24, 41, 47, 53, 59, 65-78 |
| `states/persona_state.py` | 22 | 9 | 59% | 19, 31, 45-46, 52-56 |
| `states/i18n_state.py` | 13 | 3 | 77% | 50-51, 57 |
| `states/notifications_state.py` | 22 | 2 | 91% | 74-75 |
| `states/base_state.py` | 31 | 7 | 77% | 21, 26, 31, 36, 41, 46, 51 |
| `states/auth_state.py` | 140 | 8 | 94% | 108, 153-155, 172-173, 232-233 |

### Pages — 60% average

| Module | Stmts | Miss | Cover | Missing Lines |
|--------|-------|------|-------|---------------|
| `WisPay/pages/approvals.py` | 22 | 9 | 59% | 13, 33, 65, 95, 120, 163, 234, 261, 299 |
| `WisPay/pages/request_detail.py` | 43 | 17 | 60% | 30, 36, 46, 58, 75, 97, 106, 144, 177, 207, 217, 228, 244, 264, 317, 339, 357 |
| `WisPay/pages/requests.py` | 40 | 15 | 62% | 28, 38, 51, 64, 78, 94, 121, 151, 167, 183, 195, 201, 211, 262, 289 |
| `WisPay/pages/request_new/wizard_page.py` | 26 | 10 | 62% | 34-55, 67, 104, 140, 162, 176, 190 |
| `WisPay/pages/request_new/step_details.py` | 19 | 7 | 63% | 39, 72, 149, 163, 195, 215-216 |
| `WisPay/pages/request_new/step_type.py` | 9 | 3 | 67% | 33-36, 55 |
| `WisPay/pages/request_new/step_review.py` | 18 | 7 | 61% | 32, 42, 52, 100, 129, 156, 171 |
| `WisPay/pages/request_new/step_documents.py` | 10 | 4 | 60% | 33-35, 104 |
| `WisPay/pages/request_new/controls.py` | 13 | 4 | 69% | 41, 66, 93, 109 |
| `WisPay/pages/errors.py` | 10 | 3 | 70% | 15, 20, 25 |
| `WisPay/pages/login.py` | 10 | 3 | 70% | 32, 46, 56 |
| `WisPay/pages/signup.py` | 13 | 4 | 69% | 29, 40, 93, 116 |
| `WisPay/pages/callback.py` | 5 | 1 | 80% | 16 |
| `WisPay/pages/logout.py` | 5 | 1 | 80% | 20 |
| `WisPay/pages/finance_review.py` | 30 | 1 | 97% | 113 |
| `WisPay/pages/__init__.py` | 16 | 0 | 100% | — |
| `WisPay/pages/admin.py` | 23 | 0 | 100% | — |
| `WisPay/pages/dashboard.py` | 30 | 0 | 100% | — |
| `WisPay/pages/payments.py` | 26 | 0 | 100% | — |
| `WisPay/pages/audit.py` | 17 | 0 | 100% | — |
| `WisPay/pages/reports.py` | 25 | 0 | 100% | — |

### Components — 77% average

| Module | Stmts | Miss | Cover | Missing Lines |
|--------|-------|------|-------|---------------|
| `WisPay/components/form_fields.py` | 27 | 20 | 26% | 39-42, 71-82, 106-118, 142-154 |
| `WisPay/components/tabs.py` | 23 | 6 | 74% | 80-108 |
| `WisPay/components/auth_layout.py` | 30 | 8 | 73% | 120, 139, 154, 176, 188, 200, 215, 234 |
| `WisPay/components/sidebar.py` | 47 | 3 | 94% | 65, 89, 102 |
| `WisPay/components/lifecycle_stepper.py` | 40 | 3 | 92% | 49, 130-131 |

## Prioritized List of Modules Needing Additional Tests

### Tier 1 — Highest Priority (States, < 50% coverage)

These are the thin UI adapter layers with the most uncovered logic. They are critical because they are the bridge between services and the UI:

1. **`states/approvals.py`** — 30% coverage (234 stmts, 164 missed). The `decide()`, `create_route()`, `load_queue()`, and `_load_selection()` methods are completely untested.
2. **`states/request_create.py`** — 38% coverage (267 stmts, 165 missed). `submit()`, `go_next()`, `handle_upload()`, `set_field()`, and `reset_wizard()` have no tests.
3. **`states/request_tracking.py`** — 34% coverage (171 stmts, 113 missed). `load_request()`, `load_audit()`, `set_filter()`, and all computed vars untested.
4. **`states/reports_state.py`** — 43% coverage (54 stmts, 31 missed). Report aggregation and KPI computation untested.
5. **`states/requests_state.py`** — 52% coverage (60 stmts, 29 missed). Filtering and sorting logic untested.
6. **`states/dashboard_state.py`** — 47% coverage (38 stmts, 20 missed). Dashboard KPI loading untested.
7. **`states/finance_review_state.py`** — 55% coverage (33 stmts, 15 missed). Bucket loading untested.
8. **`states/payments_state.py`** — 58% coverage (43 stmts, 18 missed). Payment bucket loading untested.

### Tier 2 — Medium Priority (Services, < 60% coverage or significant gaps)

1. **`WisPay/services/sql_repositories.py`** — 47% coverage (215 stmts, 113 missed). The Azure SQL repository layer has massive gaps — nearly half the SQL persistence code is untested.
2. **`WisPay/services/runtime.py`** — 78% coverage (59 stmts, 13 missed). Connection failure handling and store initialization untested.
3. **`WisPay/services/db.py`** — 81% coverage (97 stmts, 18 missed). Schema creation and Azure connection string assembly untested.
4. **`WisPay/services/request_creation.py`** — 90% coverage (218 stmts, 22 missed). Error paths in `submit_request` and `build_payment_request` untested.
5. **`WisPay/services/payment_recording.py`** — 93% coverage (71 stmts, 5 missed). Error paths untested.
6. **`WisPay/services/authentication.py`** — 96% coverage (157 stmts, 7 missed). Minor error paths untested.

### Tier 3 — Pages < 65% coverage

1. **`WisPay/pages/approvals.py`** — 59% coverage. Approval page rendering variants untested.
2. **`WisPay/pages/request_detail.py`** — 60% coverage (43 stmts, 17 missed). Detail view rendering branches untested.
3. **`WisPay/pages/requests.py`** — 62% coverage (40 stmts, 15 missed). Request list rendering variants untested.
4. **`WisPay/pages/request_new/wizard_page.py`** — 62% coverage. Wizard navigation rendering untested.
5. **`WisPay/pages/request_new/`** (step pages) — 60-67% coverage. Individual wizard step rendering untested.
6. **`WisPay/pages/errors.py`** — 70% coverage. Error page variants untested.
7. **`WisPay/pages/login.py`** — 70% coverage. Login flow rendering untested.
8. **`WisPay/pages/signup.py`** — 69% coverage. Signup flow rendering untested.

### Tier 4 — Components < 80% coverage

1. **`WisPay/components/form_fields.py`** — 26% coverage (27 stmts, 20 missed). Form field rendering components almost entirely untested.
2. **`WisPay/components/tabs.py`** — 74% coverage. Tab variant rendering untested.
3. **`WisPay/components/auth_layout.py`** — 73% coverage. Auth layout variants untested.

## Well-Covered Areas (>90%)

- **`WisPay/models/`** — 92% average. All enums, lifecycle, references, collaboration at 100%. Money, audit, and workflow models well-tested.
- **`WisPay/services/approval_workflow.py`** — 98%. Core approval logic well-covered.
- **`WisPay/services/audit_trail.py`** — 98%. Audit chaining well-covered.
- **`WisPay/services/reference_data.py`** — 100%.
- **`WisPay/services/repositories.py`** — 100%.
- **`WisPay/services/workflow_rules.py`** — 98%.
- **`WisPay/services/request_query.py`** — 99%.
- **`WisPay/services/user_context.py`** — 99%.
- **`states/auth_state.py`** — 94%. The only well-tested state.
- **`states/notifications_state.py`** — 91%.
- **`states/base_state.py`** — 77%.
- **`WisPay/styles.py`** — 100%.
- Most fixture pages and dashboard/admin/payments/audit/reports pages at 100%.
