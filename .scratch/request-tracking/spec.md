# Spec — Request tracking (`/requests`, `/requests/{number}`)

Status: ready-for-agent · Created: 2026-08-26 · Owner: agent (this iteration) · Branch: `feature/request` · Worktree: `E:/projects/WisPay-request`

## Sources read (ground truth)

- `E:/projects/WisPay-doc/CONTEXT.md` — Payment Request terminology, lifecycle, invariants 1–10.
- `E:/projects/WisPay-doc/docs/reference/backend/lifecycle-state-machine.md` — 14 canonical states (incl. **Adjustment Process**, absent from the CONTEXT diagram; ADR-0006 + this doc are authoritative), transition tables, "`Overdue` is a derived indicator, not a lifecycle state", edit-invalidation rules.
- `E:/projects/WisPay-doc/docs/reference/backend/authz-rbac.md` — 8 canonical roles, scope-based visibility ("Own/permitted scope" for Requester), "List views and notifications should mask sensitive beneficiary data unless the viewer has explicit permission".
- `E:/projects/WisPay-doc/docs/reference/backend/service-layer.md` + ADR-0005 — services pure Python, State is a thin adapter; **no documented query/read-side convention exists** (this spec defines the first one and flags it for an ADR).
- `E:/projects/WisPay-doc/docs/reference/backend/data-model.md` — display-snapshot rule; BeneficiaryReference carries `access_classification = RESTRICTED`.
- PRD §8.7/§8.9 — queue filters/sort precedents; global search keys. No pagination spec anywhere → session-scale client-side filtering is a documented decision, not an omission.
- `E:/projects/WisPay-deisgn/requests.html`, `request-detail.html`, `assets/tokens.css`, `assets/core.js` (`STATUS_META`, `can()` gates), `dashboard.html`; `docs/product/DESIGN.md` for intent rules only (prototypes supersede its divergent token/table specs).
- App repo at commit `0d83662` (clean worktree): `models/lifecycle.py` (14-state enum + transitions), `models/payment_request.py`, `models/references.py`, `models/audit.py`, `services/{reference_data,request_creation,audit_trail}.py`, `states/base_state.py` (`BaseState(rx.State)`), `states/request_create.py` (`RequestCreateState(rx.State)`, session store keys), `routers.py`, `pages/__init__.py`, `assets/layout.css:415-530` (existing queue block), `styles.py`, test conventions.

## Problem

Requests can be submitted at `/requests/new`, but nothing tracks them afterwards: `/requests` renders a placeholder with disabled filters and an honest empty state; no detail surface shows state, amounts, parties, route progress, or audit history. The sidebar's Requests link lands on that placeholder.

## Boundary (sibling efforts — do not touch)

- `feature/approval` effort (`.scratch/approval-workflow/spec.md`): SQL stores, WorkflowService/ApprovalService, `/approvals` page, planned seam edit inside `RequestCreateState.submit()`. This feature must NOT edit `states/request_create.py`, `services/authentication.py`, `services/user_context.py`, `components/auth_layout.py`, or anything under their scratch dirs.
- `auth-entra` effort: AuthState/login/callback/logout. At commit `0d83662` none of it exists; all states here extend plain `rx.State`.

## Decisions

1. **First read/query convention (flagged for future ADR):** pure functions in `WisPay/services/request_query.py` — `queue_rows(...)`, `get_request(...)`, typed errors `RequestNotFoundError`/`RequestAccessDeniedError`. Naming mirrors write-side conventions (`list_*`/`get_*`); queries take data + viewer as arguments, own zero I/O.
2. **Session-scoped honesty:** the MVP store is `RequestCreateState.submitted_requests` / `_submitted_model_store` / `_session_trail`. No durability is claimed in copy; cross-session persistence stays with the approval-workflow effort. UI never says "saved forever".
3. **Viewer scope = Requester "Own requests"** (authz-rbac): queue/detail show requests whose `requester.external_identity_id == viewer.external_identity_id`; other ids raise `RequestAccessDeniedError`. Viewer is `REQUESTER_PROTOTYPE` until auth lands (precedent: both prior specs).
4. **Masking:** list rows carry beneficiary display name only. `bank_reference`/`tax_or_employee_reference` render on detail only when present (our builder leaves bank `None` — row shows "—").
5. **Lifecycle rendering uses all 14 canonical values verbatim** (Title Case). Pill tones extend the prototype `STATUS_META`: Draft→neutral · Submitted→info · Budget Review/Compliance Review/Evidence Validation→info · Approval Pending→accent · Approved→ok · Payment in Process→accent · Paid→ok · Closed→neutral · Returned for Correction→warn · Rejected→danger · Cancelled→neutral · Adjustment Process→warn.
6. **Stepper collapses to the 7 normal-flow milestones** (Draft→Submitted→In Review→Approved→Payment in Process→Paid→Closed) exactly like the prototype; review bucket covers Budget/Compliance/Evidence/Approval-Pending. Exception states appear via pill + banner + branch glyph "×", never fabricated steps.
7. **Overdue derivation (docs specify inputs, not formula — this repo picks):** a Vendor request is Overdue when `details.due_date < today` AND state ∈ {Submitted…Payment in Process}. Rendered as `.wispay-flagchip warn` next to the status pill; employee requests show no overdue chip (no due field).
8. **Queue columns** (prototype order, adapted to stored fields): ID (type icon V/E + number, mono) · Payee (+ secondary line `{Family} · {Subtype}` replacing the prototype's user-entered title, which our aggregate does not store) · Gross (right-aligned mono) · Status pill · Flags · Submitted (date + `(Nd)` age) · Due (vendor due date or "—").
9. **Filters:** free-text search over number/payee/invoice/purpose; Status select (All + 14 states); Family select All/Vendor/Employee; Cost center select from stored dimension codes; Reset button. Default sort submitted desc. Header-click sorting, bulk-select, Export CSV: out of scope this slice.
10. **Detail tabs:** Summary (always) · Documents · Route & Approvals · Audit. Comments and Payment tabs are omitted entirely — no producing slice exists yet (Comment/PaymentRecord models unconsumed); fabricating them would violate DESIGN anti-patterns. Route & Approvals renders the honest empty note "No route yet — routing is generated after evidence validation." Documents renders "No documents recorded on the submitted version." until persistence lands.
11. **Detail header:** breadcrumb `← Back to requests / {Type} · {subtype}`; kicker `Request {number}`; H1 = beneficiary display name ("—" if empty); purpose paragraph below (em-dash fallback); warm amount panel (gross mono clamp, currency, waveform aria-label, verbatim note "WisPay records approvals and payment references; it does not move money."); meta grid Payee · Requester · Currency · Created.
12. **Audit tab** lists events with `entity_type == "PaymentRequest"` and `entity_id == str(request_id)` (the submit event today; later review/approval events join automatically as those slices land — `correlation_id` identifies one operation, not the request's history); a "Chain verified" chip renders only when `InMemoryAuditTrail.verify()` passes on the session trail.
13. **Cross-state reads use Reflex `get_state(RequestCreateState)`** from `RequestTrackingState` handlers — the sanctioned seam; underscore attrs stay encapsulated. Ticket 02 must confirm the exact async API against the `reflex-docs` skill before coding; fallback (only if get_state proves unavailable in 0.9.8): add a minimal read-only accessor method to `RequestCreateState` in a separate commit, coordinated with the sibling effort in the map issue.
14. **No pagination** (session-scale data); document decision in code comment referencing this spec.
15. **Number format stays `WPR-YYYY-NNNN`** (app precedent; docs' `REQ-…` samples are illustrative only). Detail route treats the number as opaque.

## Contracts (pinned for parallel work — implement exactly)

### Services — `WisPay/services/request_query.py` (ticket 01 owns)

```python
class RequestNotFoundError(LookupError): ...      # .number attr
class RequestAccessDeniedError(PermissionError): ...

@dataclass(frozen=True, slots=True)
class RequestQueueRow:
    request_id: UUID
    number: str                      # "" when None (drafts excluded anyway)
    payee_display: str               # beneficiary display_name or "—"
    type_label: str                  # RequestType.value
    subtype_label: str               # EmployeeRequestSubtype.value or ""
    amount: Money
    state: LifecycleState
    overdue: bool                    # decision 7
    submitted_at: datetime | None

def payee_display_of(request: PaymentRequest) -> str            # vendor→beneficiary.display_name; employee→details.employee.display_name
def is_overdue(request: PaymentRequest, *, today: date) -> bool # decision 7
@dataclass(frozen=True, slots=True)
class QueueQuery:
    search_text: str = ""; status: str = ""; family: str = ""; cost_center: str = ""   # "" = All

def queue_rows(
    requests: Sequence[PaymentRequest], *, viewer: UserSnapshot, today: date,
    query: QueueQuery = QueueQuery(),
) -> tuple[RequestQueueRow, ...]
    # scope to viewer (decision 3), exclude DRAFT, apply query filters HERE (search over
    # number / payee / invoice_number / purpose read from the aggregates; status, family,
    # cost-center exact match), sort submitted desc then number desc. Filtering lives in
    # the service so the state adapter never re-implements field logic.
def get_request(requests: Sequence[PaymentRequest], *, number: str, viewer: UserSnapshot) -> PaymentRequest
    # case-sensitive exact match on request_number; raises both error types
def format_money(value: Money) -> str                            # mirrors _format_amount: thousands sep, VND scale 0 else 2dp, "<amount> <CODE>"
def events_for_request(events: Sequence[AuditEvent], *, request_id: UUID) -> tuple[AuditEvent, ...]
    # entity_type == "PaymentRequest" AND entity_id == str(request_id); correlation_id is
    # per-operation and must NOT be the history key. Ordered by occurred_at.
```

Rules: imports limited to stdlib + `WisPay.models` (+ nothing else); no Reflex, no I/O; tz-aware datetimes. Unit tests in `tests/services/test_request_query.py` following `test_request_creation.py` style (fixed NOW, builder helpers vendor/employee aggregates via `build_payment_request`+`submit_request`): scoping, exclusion of drafts, sort order, both error paths, overdue boundaries (due==today not overdue; non-vendor never), money formatting incl. VND, event filtering.

### State — `states/request_tracking.py` (ticket 02 owns)

```python
class request_tracking_state(rx.State):
    rows: list[dict[str, str]]        # serialized RequestQueueRow: {request_id,number,payee,type_label,subtype_label,amount,state,tone,overdue("1"/""),submitted_display,age_days}
    search_text: str; status_filter: str; family_filter: str; cost_center_filter: str   # "" = All
    result_count: int
    empty_kind: str                   # "" | "no-requests" | "no-matches"
    selected_number: str              # number loaded into detail vars
    not_found: bool
    detail: dict[str, str]            # header/meta projection (decision 11 fields)
    detail_amount: dict[str, str]     # {value,currency,note,wave_label}
    stepper: list[dict[str, str]]     # 7 milestones {label,state:"done|active|future|branch"}
    summary_cards: list[dict[str, Any]]   # per-card {title, rows:[{k,v}]}
    doc_rows: list[dict[str, str]]    # honest-empty single note row when none
    route_steps: list[dict[str, str]] # empty until workflow slices land
    audit_rows: list[dict[str, str]]  # {when,actor,action,detail}
    chain_verified: bool
    load_error: str
    async def refresh_queue(self) -> None      # await self.get_state(RequestCreateState); rebuilds QueueQuery from filter vars, runs services
    async def set_search(self, value: str) -> None   # set var + refresh_queue
    async def set_status(self, value: str) -> None / set_family / set_cost_center   # same pattern
    async def reset_filters(self) -> None
    def open_detail(self, number: str) -> None # navigates rx.navigate to /requests/{number}
    async def load_detail(self) -> None        # on_load target; number read from self.router.page.params["number"] (on_load passes no path arg); fills detail vars or not_found=True
```

Serialization happens in the state (thin adapter); services stay dict-free. Cached derived vars allowed (e.g. filtered_rows) per `request_create.py` precedent.

### Pages / CSS ownership

- Ticket 03 (queue): rewrite `WisPay/pages/requests.py` binding `request_tracking_state`; keep shell()/toolbar/heading classes already in layout.css (`wispay-request-toolbar/-heading`, `wispay-requests-filter-section/-filters/-filter-heading/-filter-note/-filter-grid/-filter-field/-filter-label/-filter-control`, `wispay-request-empty/-empty-title/-empty-copy`); append ONLY under the pre-seeded banner `/* ==== Requests queue table (/requests) — ticket 03 owns ==== */` new classes prefixed `wispay-queue-` (bulk count line, `wispay-queue-table` mirroring `.ds-table` anatomy: th mono 11 uppercase muted / td 13px padding / hover bg surface / right-aligned mono `td.amt` / `data-th` on every td for ≤768px card fallback / type-icon / pillstat+flagchip ports named `wispay-pill tone-*`, `wispay-flagchip warn`). Copy verbatim: heading eyebrow "Payment Request queue", H1 "Requests", lede "Track every payment request you have submitted, from intake to payment record."; empty no-requests title "No requests yet" copy "Start by creating a new payment request."; no-matches title "No requests match your filters" copy "Adjust or clear filters to see more results."; buttons "New Payment Request", "Reset filters".
- Ticket 04 (detail): new `WisPay/pages/request_detail.py`; edits `routers.py` (add dynamic route `/requests/[number]` — plain Reflex segment syntax, no `:key` — between `/requests/new` and `/404`; page title via default or `d-*` heading), `WisPay/pages/__init__.py` export; append CSS ONLY under `/* ==== Request detail (/requests/{number}) — ticket 04 owns ==== */` prefixed `wispay-detail-` (breadcrumb, kicker, title-row, meta grid 4-col→2-col≤640px, warm amount panel + wave bars, banners, stepper 7 nodes, tabs bar + panels, kv-rows, audit feed, sticky-bottom action bar skeleton omitted this slice). Responsive: header 1-col ≤900px; meta 2-col + h1 32px ≤640px; kv-rows stack ≤430px. Not-found inline empty state with back link.
- Shared rules: semantic `rx.el.*`, class_name strings only (pages do NOT import styles.py), stable ids `id="q-*"`/`id="d-*"` for Playwright, aria-live on filter result count + load errors, focus-visible preserved, reduced-motion respected, min touch target 44px, tokens only `--ws-*`.

### E2E + validation (ticket 05 — orchestrator-owned)

`tests/e2e/test_request_tracking.py`: submit a vendor request through the wizard → `/requests` shows one row (number WPR-, status Submitted, gross formatted) → filters reduce/hide it → click row opens `/requests/{number}` → detail asserts breadcrumb/kicker/H1=payee/amount panel text/stepper active node 2/audit tab contains "Submitted"/chain-verified chip → direct navigation to unknown number renders not-found state. Desktop 1440×900 + mobile 390×844 sweeps assert no horizontal scroll and no console/page errors. Then full gate: `uv run pytest tests/services tests/models`, `bash scripts/validate.sh`, browser review protocol per AGENTS.md.

## Files (ownership map — no overlaps)

| Ticket | New files | Edits |
| --- | --- | --- |
| 01 | `WisPay/services/request_query.py`, `tests/services/test_request_query.py` | — |
| 02 | `states/request_tracking.py` | — |
| 03 | — | `WisPay/pages/requests.py` (rewrite), `assets/layout.css` (queue banner section only) |
| 04 | `WisPay/pages/request_detail.py` | `WisPay/routers.py`, `WisPay/pages/__init__.py`, `assets/layout.css` (detail banner section only) |
| 05 | `tests/e2e/test_request_tracking.py` | integration fixes anywhere needed |

## Acceptance criteria

1. `uv run pytest tests/services/test_request_query.py` green: scoping, drafts excluded, sorting, error paths, overdue boundary, VND formatting, event filtering.
2. `/requests` renders live session submissions with working search/status/family/cost-center filters, count line, honest empty states, pill+overdue chips, mobile card fallback ≤768px.
3. `/requests/{number}` renders header, amount panel, stepper, Summary/Documents/Route/Audit sections per decisions 10–12; unknown number → not-found state; another viewer's number → access-denied surfaced honestly (not-found presentation, log keeps distinction).
4. No edits outside the ownership map; `bash scripts/validate.sh` passes clean; e2e suite green at both viewports with zero console errors.
5. UI copy claims nothing about durability; sample/prototype labels visible where fixed data used.

## Out of scope (tracked elsewhere)

Decision actions/route generation/SQL persistence (approval-workflow map #3), auth identity cutover (map #6/#7), comments/payment recording surfaces, CSV export, header-sort, dashboard KPI wiring.
