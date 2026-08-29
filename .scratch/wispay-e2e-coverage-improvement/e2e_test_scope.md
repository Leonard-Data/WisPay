# E2E Test Scope — WisPay Payment Request Portal

## 1. Overview

**Application**: WisPay — internal portal for Vendor and Employee Payment Requests
**Framework**: Reflex 0.9.8 (Python 3.14, Pydantic v2, Radix Themes + Tailwind v4, Azure SQL/SQLite)
**Browser testing**: Playwright (sync API via pytest)
**Auth bypass**: `WISPAY_E2E_AUTH_BYPASS=1` skips the `AuthState.guard` gate for headless E2E
**Demo mode**: `WISPAY_DEMO_MODE=1` seeds S01–S16 fixtures (16 requests, 8 personas, audit events, payments)
**Test marker**: `pytest.mark.e2e` — excluded by default (`-m 'not e2e'` in pyproject.toml addopts)

## 2. Canonical Routes (from `WisPay/routers.py`)

| # | Route | Title | Auth-guarded? | Page component | Lifecycle states exercised |
|---|-------|-------|---------------|----------------|---------------------------|
| 1 | `/` | Dashboard | Yes (guard + persona + dashboard refresh) | `dashboard_page` | — |
| 2 | `/requests` | Requests | Yes (guard + request_tracking refresh) | `requests_page` | All tracked states |
| 3 | `/requests/[number]` | Request Detail | Yes (guard + load_detail) | `request_detail_page` | All states (via dynamic param) |
| 4 | `/requests/new` | New Payment Request | Yes (guard only) | `request_new_page` | Draft → Submitted |
| 5 | `/approvals` | Approvals | Yes (guard + approvals load) | `approvals_page` | Approval Pending, Approved |
| 6 | `/finance-review` | Finance Review | Yes (guard + FinanceReview refresh) | `finance_review_page` | Budget/Compliance/Evidence/Approval buckets |
| 7 | `/payments` | Payment Recording | Yes (guard + Payments refresh) | `payments_page` | Approved → Payment in Process → Paid |
| 8 | `/admin` | Sample Configuration | Yes (guard + Admin refresh) | `admin_page` | — |
| 9 | `/audit` | Audit Trail | Yes (guard + Audit refresh) | `audit_page` | All (audit stream) |
| 10 | `/reports` | Reports & Exports | Yes (guard + Reports refresh) | `reports_page` | — |
| 11 | `/login` | Sign in | No | `login_page` | — |
| 12 | `/signup` | Request access | No | `signup_page` | — |
| 13 | `/auth/callback` | Completing sign-in | No (on_load callback) | `callback_page` | — |
| 14 | `/logout` | Signing out | No (on_load logout) | `logout_page` | — |
| 15 | `/404` | Page Not Found | No | `not_found_page` | — |
| 16 | `/500` | Something Went Wrong | No | `server_error_page` | — |
| 17 | `/503` | Temporarily Unavailable | No | `unavailable_page` | — |

### Unknown route (routing)
- Any path not matching the above → should render the not-found page or Reflex default 404.

## 3. Existing E2E Test Coverage (tests/e2e/)

### `test_ui_smoke.py` (2 tests)
- **`test_index_page_renders_across_viewports`**: Dashboard at `/` — title, heading "A clear place to start", "Start a new Payment Request" link → `/requests/new`, nav links visible, no horizontal scroll at 1440×900 and 390×844, mobile "Open navigation" button visible, no browser errors.
- **`test_shell_sidebar_is_responsive_and_interactive`**: `/requests` page — sidebar width (264px desktop / 72px collapsed), mobile drawer open/close with backdrop, sidebar group toggles, viewport breakpoints: 1440, 1280, 1024, 768, 390, 375.

### `test_approvals.py` (2 tests)
- **`test_approvals_route_decide_and_timeline`**: Seeds a Submitted Vendor request via service layer, navigates to `/approvals`, generates approval route, reviews Line Manager step, verifies return-without-reason guard, approves the step, checks decision recorded.
- **`test_approvals_mobile_layout`**: Seeds a Submitted request, navigates to `/approvals` at 390×844, verifies no horizontal scroll.

### `test_request_create.py` (3 tests)
- **`test_wizard_happy_path_submits_vendor_request`**: Full wizard flow: Vendor payment → Details → Documents (PDF upload) → Review → Submit. Verifies gross amount calculation (11,000,000 VND), request number starts with "WPR-", no horizontal scroll.
- **`test_wizard_blocks_empty_details_with_field_errors`**: Continues without selecting type → error "Select a request type first."; selects Reimbursement → Continue → field errors visible.
- **`test_wizard_responsive_at_mobile_width`**: Wizard at 390×844 — step bar collapses to 2-column grid, no horizontal scroll.

### `test_request_tracking.py` (2 tests)
- **`test_queue_lists_submitted_request_with_filters_and_pills`**: Submits a Vendor request, navigates to `/requests`, verifies row visibility with Submitted pill, amount in VND, queue count, search filter (no-match state), status filter, click-through to detail page, breadcrumb.
- **`test_detail_renders_header_stepper_audit_and_not_found`**: Submits request, navigates to `/requests/[number]`, verifies 7-step lifecycle stepper with active step, Audit tab with Submitted event + "Chain verified", not-found path for `WPR-1999-9999`, responsive at both viewports.

### Coverage gaps identified
- **Error pages** (`/404`, `/500`, `/503`): Not covered by E2E (only unit-tested in `tests/test_error_pages.py`).
- **Public auth routes** (`/login`, `/signup`, `/auth/callback`, `/logout`): Not covered by E2E.
- **Finance Review** (`/finance-review`): Not covered by E2E.
- **Payments** (`/payments`): Not covered by E2E.
- **Admin** (`/admin`): Not covered by E2E.
- **Audit** (`/audit`): Not covered by E2E.
- **Reports** (`/reports`): Not covered by E2E.
- **Dashboard** (`/`): Only covered for smoke/title/sidebar-nav; no KPI, persona card, activity feed, or shortcut card verification.

## 4. E2E Test Scope — Routes & Viewport Matrix

### Viewport contracts (from `DESIGN.md` §6)
- **Desktop**: 1440×900 — primary review size
- **Mobile**: 390×844 — mobile review size
- **Additional breakpoints**: 360, 430, 600, 768, 820, 1024, 1200, 1366, 1920 — no horizontal scroll at any
- **Touch targets**: ≥44px minimum
- **Sidebar**: 264px desktop, becomes drawer at 1024px, collapses to 72px when toggled

### Per-route E2E scope

#### Route 1: `/` (Dashboard)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Dashboard · WisPay"
- [ ] Heading: "A clear place to start"
- [ ] Info banner with "Sample configuration" + fixture disclaimer
- [ ] KPI row visible with sample metrics (Requests in window, Approved, Median cycle time, Over-budget exceptions)
- [ ] "New Payment Request" button (disabled per t4; title="t5 wires the navigation")
- [ ] "View requests" link → `/requests`
- [ ] Lifecycle explainer card with records-not-moves language
- [ ] Persona card with 4 persona chips (Line Manager active)
- [ ] Recent activity card with audit rows
- [ ] Sidebar nav: Dashboard, Requests, New Request, Approvals, Finance Review, Payments, Audit visible
- [ ] No browser console errors
- [ ] No horizontal overflow scroll
- [ ] Mobile: "Open navigation" button visible, sidebar becomes drawer

#### Route 2: `/requests` (Requests Queue)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Payment Requests · WisPay"
- [ ] Heading: "Requests"
- [ ] Toolbar with "New Payment Request" primary link → `/requests/new`
- [ ] Filter card: Search, Status, Family, Cost center controls
- [ ] Queue table with headers: ID, Payee, Gross, Status, Flags, Submitted, Due
- [ ] Demo seed data visible (S01–S16 lifecycle states)
- [ ] Status pills with correct tones per lifecycle state
- [ ] Count badge updates with filters
- [ ] Empty state for no-match search: "No requests match your filters" + "Clear all filters"
- [ ] Row click navigates to `/requests/[number]`
- [ ] No horizontal overflow

#### Route 3: `/requests/[number]` (Request Detail)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] For each demo-seeded request (S01–S16): detail page renders
- [ ] Breadcrumb: "← Back to requests / [type]"
- [ ] Header: request number kicker, status pill, payee heading, purpose, meta grid (Payee, Requester, Currency, Created)
- [ ] Gross amount panel with waveform, currency, value, and records-not-moves note
- [ ] 7-step lifecycle stepper with correct active step
- [ ] Tab bar: Summary, Documents, Route & Approvals, Audit (role="tablist")
- [ ] Summary tab: parties, accounting dimensions, amount breakdown cards
- [ ] Documents tab: checklist with "no route yet" state when empty
- [ ] Route & Approvals tab: route steps or empty state
- [ ] Audit tab: timestamp, actor, action, chain verification chip
- [ ] Not-found path: `/requests/WPR-1999-9999` → "Request not found"
- [ ] No horizontal overflow

#### Route 4: `/requests/new` (Create Request Wizard)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "New Payment Request · WisPay"
- [ ] Step bar: 4 steps (Type, Details, Documents, Review), current step highlighted
- [ ] Step 1: Vendor payment card + 4 employee type cards with copy
- [ ] Step 2: Details form fields (title, vendor_name, invoice_number, dates, dropdowns, money fields, purpose) with gross auto-calculation
- [ ] Step 3: Document checklist with file upload per slot, "is-met" class on attached
- [ ] Step 4: Review summary with amount, purpose, parties
- [ ] Submit → confirmation panel with request number
- [ ] Back/Continue navigation between steps
- [ ] Field validation errors on empty submit
- [ ] Mobile: step bar collapses to 2-column grid
- [ ] No horizontal overflow

#### Route 5: `/approvals` (Approvals Tracking)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Approvals · WisPay"
- [ ] Heading: "Approvals"
- [ ] Actor switcher with sample actors (Line Manager, Executive Approver)
- [ ] Route generation tool: input field, "Generate approval route" button
- [ ] Pending queue table: Number, Request, Amount, Requester, Approver role, Due, Review & decide
- [ ] Empty state: "No approvals are waiting on you"
- [ ] Decision panel: selected request metadata, reason textarea, Approve/Return/Reject buttons
- [ ] Return guard: "reason is required" when no reason provided
- [ ] Timeline card with frozen route steps
- [ ] No horizontal overflow

#### Route 6: `/finance-review` (Finance Review Queue)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Finance Review · WisPay"
- [ ] Heading: "Review queues"
- [ ] Info banner: "Sample configuration" + prototype defaults notice
- [ ] KPI row: Open in review, Budget exceptions, Compliance returned, Approval pending
- [ ] Four bucket cards: Budget Review, Compliance Review, Evidence Validation, Approval Pending
- [ ] Each bucket: table with ID, Payee, Gross, Stage, Review button
- [ ] Empty bucket state: "No requests waiting in this bucket."
- [ ] Status pills with correct tones (OK/warn/info)
- [ ] No horizontal overflow

#### Route 7: `/payments` (Payment Recording)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Payment Recording · WisPay"
- [ ] "Records, not movement" banner with no-money-moved tone
- [ ] KPI row: Ready to start, In process, Paid, Closure due
- [ ] Queue card: table with ID, Payee, Approved amount, Stage, Start/Record/Close buttons
- [ ] Actions panel explaining Start/Record/Close with permission-scoped language
- [ ] Payment operator actions with title tooltips (disabled state notes)
- [ ] No horizontal overflow

#### Route 8: `/admin` (Sample Configuration)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Sample Configuration · WisPay"
- [ ] "Sample configuration — not policy" warning banner
- [ ] Approval thresholds matrix card
- [ ] Route simulator card (disabled Generate button)
- [ ] Document requirements matrix card
- [ ] Persona matrix card: 8 persona tiles
- [ ] No horizontal overflow

#### Route 9: `/audit` (Audit Trail)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Audit Trail · WisPay"
- [ ] Heading: "Audit trail"
- [ ] "Append-only" info banner with hash-chain explanation
- [ ] Search card: Request number, Actor, Action, Window filters
- [ ] Audit stream card with sample rows (timestamp, action, actor, scope)
- [ ] Count label: "N events · chain verified"
- [ ] No horizontal overflow

#### Route 10: `/reports` (Reports & Exports)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Reports & Exports · WisPay"
- [ ] Heading: "Reports & exports"
- [ ] Info banner: "Sample metrics" + prototype disclaimer
- [ ] KPI row: Requests in window, Approved, Median cycle time, Over-budget exceptions
- [ ] Spend by cost center card with bar rows
- [ ] Spend by family card (Vendor vs Employee)
- [ ] Spend by period card (trailing 6 months)
- [ ] Export center card with permission-scoped CSV labels (disabled Download buttons)
- [ ] No horizontal overflow

#### Route 11: `/login` (Sign In)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Sign in · WisPay"
- [ ] Brand mark / wordmark visible
- [ ] Heading: "Sign in"
- [ ] Lede: "WisPay uses your corporate Microsoft account through single sign-on."
- [ ] "Sign in with Microsoft" primary button (bound to `AuthState.start_login`)
- [ ] "Request access" ghost link → `/signup`
- [ ] No horizontal overflow

#### Route 12: `/signup` (Request Access)
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] Page title: "Request access · WisPay"
- [ ] Heading: "Request access"
- [ ] Lede: "Ask a WisPay administrator..."
- [ ] Form fields: Work email, Full name, Business unit, Justification
- [ ] "Submit request" primary button → shows submitted notice
- [ ] Submitted notice: "Request recorded" + admin review explanation
- [ ] "Back to sign in" link → `/login`
- [ ] No horizontal overflow

#### Routes 13–17: Auth Flow & Error Pages
**Viewports**: 1440×900, 390×844
**Checks**:
- [ ] `/auth/callback`: spinner "Completing sign-in…" visible
- [ ] `/logout`: spinner "Signing out…" visible
- [ ] `/404`: "Page Not Found" content with code
- [ ] `/500`: "Something Went Wrong" content with code
- [ ] `/503`: "Temporarily Unavailable" content with code
- [ ] Direct navigation to `/404`, `/500`, `/503` renders correct error content
- [ ] Unknown route (e.g., `/nonexistent`) renders not-found page

#### Auth gate behavior
- [ ] Without `WISPAY_E2E_AUTH_BYPASS=1`: unauthenticated browser visiting `/dashboard` redirects to `/login`
- [ ] With bypass active: all guarded routes render without redirect

## 5. Cross-Cutting Concerns

### Accessibility
- [ ] All pages have unique `<title>` tags matching route titles
- [ ] Proper heading hierarchy (h1 → h2 → h3)
- [ ] Role attributes on interactive elements (role="tablist", role="tab", role="status", role="alert")
- [ ] ARIA labels on form controls (aria-label, aria-describedby)
- [ ] Focus management on tab switches and sidebar toggles
- [ ] Color contrast compliance (dark text on light background per token.css)
- [ ] No `prefers-reduced-motion` violations (animations are subtle: 150-200ms)

### Visual / Design System Compliance (per `DESIGN.md`)
- [ ] 264px sidebar on desktop; 72px when collapsed
- [ ] Crimson (`#cf000f`) for primary action buttons only
- [ ] No horizontal scroll at all tested breakpoints
- [ ] All touch targets ≥44px
- [ ] Tables collapse to readable stacked rows below 768px (data-th labels)
- [ ] Payment recording surfaces use "record"/"external reference" language — no "transfer"/"debit"/"sent"
- [ ] Admin surfaces labeled "Sample configuration — not policy"
- [ ] Metrics labeled as sample/prototype, not production claims

### Browser Error Capture
- [ ] No `console.error` messages on any route
- [ ] No unhandled `pageerror` exceptions
- [ ] No network failures (4xx/5xx responses) on critical resources

### Data Integrity
- [ ] Demo seed data (S01–S16) visible when `WISPAY_DEMO_MODE=1`
- [ ] Request numbers follow `WPR-2026-DEMO-NN` pattern
- [ ] All 14 canonical lifecycle states represented in demo data
- [ ] Audit trail shows Submitted event + chain verification on detail pages
- [ ] Requester ≠ approver in all seeded data (CONTEXT.md invariant 1)

## 6. Environment Setup

### Server startup
```bash
WISPAY_DEMO_MODE=1 WISPAY_E2E_AUTH_BYPASS=1 WS_DB_URL=sqlite:///./.wispay-e2e.db \
  uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1
```

### Test execution
```bash
WISPAY_E2E_AUTH_BYPASS=1 WISPAY_E2E_BASE_URL=http://127.0.0.1:3000 \
  uv run pytest -m e2e tests/e2e/ -v --tb=short
```

### Test markers (from `pyproject.toml`)
- `e2e`: browser-based end-to-end tests (requires running Reflex app)

### Conftest fixtures (from `tests/e2e/conftest.py`)
- `base_url`: session-scoped, reads `WISPAY_E2E_BASE_URL` (default `http://127.0.0.1:3000`)
- `browser`: session-scoped Chromium instance (headless unless `WISPAY_E2E_HEADED=1`)
- `page`: function-scoped desktop 1440×900 page, captures `pageerror` and `console.error`
- `browser_errors`: function-scoped list of error strings, asserted empty at test end
- `pytest_runtest_makereport`: exposes report to fixtures for failure screenshot capture

## 7. New Test Files to Create

Based on coverage gaps, the following new E2E test files should be added to `tests/e2e/`:

1. **`test_error_routes.py`** — E2E coverage for `/404`, `/500`, `/503`, and unknown routes at both viewports
2. **`test_auth_routes.py`** — Login, signup, callback, logout, and auth-gate redirect behavior
3. **`test_dashboard.py`** — Full dashboard surface: KPIs, persona cards, activity feed, lifecycle explainer, shortcut card
4. **`test_finance_review.py`** — Finance review queue: four buckets, KPIs, table rendering, empty states
5. **`test_payments.py`** — Payment recording queue: KPIs, table with operator actions, records-not-moves banner
6. **`test_admin.py`** — Admin configuration: thresholds, route simulator, doc requirements, persona matrix
7. **`test_audit.py`** — Audit trail search, stream rendering, chain verification label
8. **`test_reports.py`** — Reports & exports: KPIs, spend bars, export center
9. **`test_responsive_contract.py`** — Dedicated responsive test across all DESIGN.md breakpoints (360, 430, 600, 768, 820, 1024, 1200, 1366, 1440, 1920) for key routes

## 8. Existing Test Files to Extend

1. **`test_ui_smoke.py`**: Extend dashboard coverage beyond smoke — add KPI, persona, activity, lifecycle explainer assertions
2. **`test_request_create.py`**: Add viewport coverage for step 2 (Details) and step 3 (Documents) at mobile width
3. **`test_request_tracking.py`**: Add detail tab switching (Documents, Route & Approvals) for seeded requests in mid-lifecycle states

## 9. Security / Domain Invariant Checks (CONTEXT.md)

E2E tests should assert the following invariants at the UI layer:

- [ ] Dashboard "New Payment Request" button is disabled (t4 prototype state — t5 wires navigation)
- [ ] Payments page uses "Record" language, never "Transfer" or "Send"
- [ ] Approvals page footnote: "Recording a decision is audit evidence. It never moves money"
- [ ] Admin page banners all say "Sample configuration — not policy"
- [ ] All sample metrics are labeled as prototype/fixture, not production claims
- [ ] Disabled controls in admin/simulator have explanatory title attributes
