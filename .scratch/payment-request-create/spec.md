# Spec — Payment Request create step (`/requests/new`)

Status: ready-for-agent · Created: 2026-08-25 · Owner: agent (this iteration)

## Sources read (ground truth)

- `E:/projects/WisPay-doc/CONTEXT.md` — terminology, categories, unified lifecycle, core invariants 1–10.
- `E:/projects/WisPay-doc/wispay-delivery-plan.md` — Phase 2 "Request capture" scope.
- `E:/projects/WisPay-doc/docs/reference/backend/service-layer.md` — `PaymentRequestService` ownership; standard write method shape; State adapter rules.
- `E:/projects/WisPay-doc/docs/adr/0005-service-reflex-state-seam.md` — services own business logic; State is a thin UI adapter; no audit writes outside audited service boundary.
- `docs/product/DESIGN.md` (checked-in snapshot) — visual/interaction contract.
- `E:/projects/WisPay-deisgn/new-request.html` — canonical source example for this screen (wizard steps, classes, copy, behaviors).
- Repo: `CONVENTIONS.md`, existing models under `WisPay/models/`, `assets/globals.css`/`layout.css`, `WisPay/styles.py`.

**Environment note (surface, do not silently fix):** AGENTS.md names the design-system source at `C:\Users\binh.phung\projects\WisPay-Design-System`; on this machine the package lives at `E:\projects\WisPay-deisgn\` (directory name misspelled). Content matches the checked-in DESIGN.md snapshot. No conflict found in substance.

## Problem

The dashboard and the requests queue already link to `/requests/new`, but the route does not exist (404). Phase 2 "Request capture" needs the create/submission wizard: dynamic Vendor/Employee forms, calculations, drafts-in-session, validation, duplicate warnings, and submission with audit trail.

## Decisions

1. **4-step wizard, mirroring the source example exactly:** 1 Type → 2 Details → 3 Documents → 4 Review & submit. Copy, step names, and component shapes come from `new-request.html`; visual values come from `assets/design-tokens.css` tokens via `WisPay/styles.py`.
2. **Services hold the logic** (ADR-0005): new pure-Python modules under `WisPay/services/`, zero `reflex` imports. `states/request_create.py` is a thin adapter: collect input → call service → translate typed errors.
3. **Documents step is real but session-scoped:** file capture via Reflex upload handlers with MIME/size validation (PDF/PNG/JPG/XLSX, ≤10 MB), SHA-256 checksum, stored under the app upload dir. Durable/blob storage, malware-scan pipeline, and Azure DI extraction are **out of scope** (issue 05).
4. **Submission enforces invariant 2** ("cannot submit without required fields and documents"): the service owns a provisional document-requirement matrix (below), labeled sample configuration pending Phase 0 sign-off. Missing required docs block submit with visible reasons.
5. **Audit trail is real but non-durable:** pure hash-chained `AuditEvent` construction (canonical JSON → SHA-256 chain, genesis `0…0`) held in session memory. Tamper-evident verification included. Durable append via AuditService + SQL lands with issue 05. This honors "every submission is audit logged" within the session boundary and nothing pretends more.
6. **Approval-route preview omitted:** WorkflowService route generation is Phase 3. Fabricating a route would violate DESIGN.md anti-patterns. Review step states plainly that routing is generated at submission once controls land. (Source prototype showed a demo route; we do not copy fabricated data.)
7. **No "Save draft" button this iteration:** durable drafts need a repository. The in-progress draft persists in session state while navigating; explicit durable save is issue 05. (Omitting beats faking.)
8. **Settlement subtype:** supported only when a previously submitted Advance exists in the same session; otherwise the source's honest empty state ("A paid cash advance must be open before it can be settled."). Linked-advance balance math uses `Decimal` via service helpers.
9. **Duplicate warning (Vendor):** same-session scan over submitted vendor requests matching beneficiary display name + invoice number; surfaces a warning banner at Review. Cross-session dedup needs persistence (issue 05).
10. **Requester identity:** no auth yet; a fixed prototype requester `UserSnapshot` supplied by `reference_data.py`, visibly labeled sample configuration. Separation-of-duties enforcement is unaffected here (requester cannot approve — approval does not exist yet).
11. **Money handling:** amounts entered as decimal strings; VND forced to scale 0, USD/EUR scale 2. Gross = net + VAT amount (model enforces net+vat==gross; UI computes live preview with `Decimal`, never floats).
12. **Component approach:** follow the existing codebase convention (`rx.el.*` + `wispay-*` classes + token CSS), not a second Radix/Buridan styling path. Buridan index was fetched (2026-08-25); its Field/Input/Select/Button concepts informed semantics; no new Buridan dependency introduced.

## Provisional document-requirement matrix (sample configuration — not policy)

| Family | Subtype | Required | Optional |
| --- | --- | --- | --- |
| Vendor | standard | Invoice | Purchase order, Contract, Goods receipt, Service acceptance |
| Employee | Reimbursement | Receipt | Expense statement |
| Employee | Advance | Activity evidence | — |
| Employee | Advance settlement | Expense statement | — |
| Employee | Internal expenditure | Policy approval evidence | — |

Keys map to `DocumentCategory` enum values; matrix lives in `WisPay/services/reference_data.py` as the single configuration point.

## Route & information architecture

- New route `/requests/new` — title "New Payment Request · WisPay", registered in `routers.py` between `/requests` and `/404`.
- Page header: eyebrow `Request intake` (mono uppercase), H1 `Create payment request`, lede `Build a complete request, preview its approval route, and submit it for review.` → lede adjusted to honest copy: `Build a complete request and submit it for review.` + `Draft` pill badge (warm surface, mono uppercase, dot).
- Step bar: numbered nodes 1–4 with active (black underline + filled num), done (fg-2), future (faded) states per source CSS; future steps disabled; completed steps clickable back.
- Sticky action bar bottom: Back (ghost, step>1) · primary Continue (steps 1–3) / Submit for approval (step 4). No second solid primary per viewport.
- Success state replaces wizard: confirmation panel with mono request number, lifecycle state `Submitted`, next-step copy; link back to `/requests`.
- `aria-live` announcements on step change and validation outcomes; focus moves to step heading on navigation; first invalid field focused on failed validation.

### Step 1 — Type

- Group "Supplier payments": 1 card (Vendor payment). Group "Employee payments": 4 cards (Reimbursement, Cash advance, Advance settlement, Internal expenditure). Card: title, one-line copy, Selected/Choose state chip; warm surface + inset ring when selected.

### Step 2 — Details (dynamic by selection)

Sections (source order): Request / Accounting & amount / Business purpose.
- Common: title (full width), currency select (VND/USD/EUR), purpose textarea.
- Vendor adds: vendor name (text, becomes beneficiary display name), invoice number, invoice date, due date (≥ invoice date), net amount, VAT amount; gross preview card (live `net + vat`, warm surface, aria-live).
- Employee adds: subtype-specific fields — Reimbursement: merchant/payee, expense date, policy category; Advance: activity start/end (end ≥ start), requested payment date; Settlement: linked advance select (session-paid advances) + balance summary rows; Internal: policy category. Claimed amount = net amount field.
- Accounting: legal entity (sample select), cost center (sample select), project (optional text), expense category (sample select), OPEX/CAPEX select, budget period (month, defaults to current month).
- Field errors render adjacent (`field-error`), `aria-invalid` + `aria-describedby`; Required/Optional mono tags on every label.

### Step 3 — Documents

- Checklist rows: required dot (danger→success when met), title, meta line (mono filename·size or "Required before submission"/"Optional support"), Choose file (hidden input + secondary small button) or Attached pill + Remove ghost button.
- Upload validation errors inline (`role="alert"`): extension whitelist, ≤10 MB. Accepted-types note card.

### Step 4 — Review

- Error panel (danger tint, role=alert): count lead + list; buttons Edit details / Add documents jump to steps.
- Warning panel (warn tint): duplicate-hit messages, over-scale hints.
- Summary card (`summary-row` grid, right-aligned values): Title, Type, Payee, Gross amount (mono), Cost center, Currency, Accounting period.
- Note copy: submitting freezes request data; corrections later go through Return-for-correction; WisPay approves and records payments, never initiates money movement (DESIGN.md voice).

## Contracts (pinned for parallel work)

### Service layer — `WisPay/services/` (new package)

```python
# reference_data.py
REQUESTER_PROTOTYPE: UserSnapshot  # fixed sample requester
LEGAL_ENTITIES / COST_CENTERS / EXPENSE_CATEGORIES / PAYMENT_TERMS / PAYMENT_METHODS: tuple[SampleOption, ...]
POLICY_CATEGORIES: tuple[str, ...]
CURRENCIES: tuple[tuple[str, int], ...]          # (code, decimal_scale); VND→0, USD/EUR→2
def doc_requirements(family: str, subtype: str) -> tuple[DocRequirement, ...]
@dataclass(frozen=True) DocRequirement: key: str; label: str; category: DocumentCategory; required: bool
@dataclass(frozen=True) SampleOption: code: str; name: str

# request_creation.py
class DraftCommand(WisPayBaseModel): ...            # every raw form field, typed; strings unparsed
class FieldIssue(WisPayBaseModel): field: str; message: str
class ValidationOutcome(WisPayBaseModel):
    field_issues: tuple[FieldIssue, ...]; blocking: tuple[str, ...]; warnings: tuple[str, ...]
def validate_draft_command(cmd: DraftCommand) -> ValidationOutcome      # cheap, per-field, pre-model
def build_payment_request(cmd, *, requester: UserSnapshot, now: datetime) -> PaymentRequest  # raises pydantic.ValidationError
def submit_request(req: PaymentRequest, *, actor: UserSnapshot, now: datetime,
                   request_number: str) -> SubmissionResult             # guards: state==DRAFT, docs satisfied
@dataclass(frozen=True) SubmissionResult: request: PaymentRequest; audit_event: AuditEvent
def duplicate_scan(existing: Sequence[PaymentRequest], cmd: DraftCommand) -> tuple[str, ...]
def parse_money(text: str, currency: str) -> Money                      # raises ValueError with user-safe msg
def gross_of(net: Money, vat: Money) -> Money

# audit_trail.py
GENESIS_HASH: str                                        # "0"*64
def canonical_payload(payload: dict[str, object]) -> str # stable key-sorted JSON
def chain_hash(previous_hash: str, payload_json: str) -> str  # sha256 hexdigest
class InMemoryAuditTrail:                                # session-scoped append-only chain
    def __init__(self) -> None
    def append(self, *, entity_type: str, entity_id: str, actor: UserSnapshot,
               action: AuditAction, occurred_at: datetime, new_value: str | None = None,
               correlation_id: str, retention_policy_id: UUID) -> AuditEvent
    def events(self) -> tuple[AuditEvent, ...]
    def verify(self) -> bool                             # recompute chain; tamper check
```

Rules: services import stdlib + Pydantic + `WisPay.models` only. No Reflex, no I/O besides the upload checksum helper receiving bytes. All datetimes timezone-aware.

### State — `states/request_create.py` (pinned API)

```python
class request_create_state(rx.State):
    step: int                       # 1..4, default 1
    family: str; subtype: str       # "" until chosen
    title: str; purpose: str; currency: str          # currency default "VND"
    net_text: str; vat_text: str
    vendor_name: str; invoice_number: str; invoice_date: str; due_date: str
    merchant: str; expense_date: str; policy_category: str
    activity_start: str; activity_end: str; requested_payment_date: str
    linked_advance_id: str
    legal_entity: str; cost_center: str; project: str
    expense_category: str; classification: str       # OPEX|CAPEX
    budget_period: str
    field_errors: dict[str, str]; blocking: list[str]; warnings: list[str]
    uploads: list[dict]             # {key, file_name, size_bytes, sha256_hex}
    upload_errors: dict[str, str]
    submitted_number: str           # "" until success
    gross_preview: str              # formatted via service Decimal math
    # handlers
    def select_type(self, family: str, subtype: str) -> None
    def set_field(self, name: str, value: str) -> None        # whitelisted names only
    def recalc_gross(self) -> None                            # called by set_field on amount fields
    def handle_upload(self, files: list[rx.UploadFile]) -> None
    def remove_upload(self, key: str) -> None
    def go_next(self) -> None               # gates: step1 family chosen; step2 validate_draft_command field_issues empty; step3 required docs met
    def go_back(self) -> None; def go_to_step(self, n: int) -> None   # backward only for completed steps
    def submit(self) -> None                # full validate → build → submit_request → audit append → submitted_number set
    def reset_wizard(self) -> None
```

Session store of submitted requests lives on the same state class (`submitted_requests: list[dict]`: number, title, family, subtype, gross, currency, state, submitted_at) so settlement linkage and duplicate scan have data; queue-page wiring stays out of scope.

### Files (ownership map — no overlaps between agents)

| Area | Files |
| --- | --- |
| Services + unit tests | `WisPay/services/__init__.py`, `reference_data.py`, `request_creation.py`, `audit_trail.py`; `tests/services/test_reference_data.py`, `test_request_creation.py`, `test_audit_trail.py` |
| State | `states/request_create.py` |
| Page/UI | `WisPay/pages/request_new.py`; edits: `WisPay/pages/__init__.py`, `routers.py`, `assets/layout.css` (append `.wispay-new-*` section), `WisPay/styles.py` (append wizard namespaces) |
| E2E | `tests/e2e/test_request_create.py` |

CSS uses only `--ws-*` tokens (see `styles.py::Tokens`); class prefix `wispay-new-`; responsive breakpoints 768px (single column grids) and 560px (stacked step bar, stacked actions) per source media queries; `prefers-reduced-motion` honored; min touch target 44px; focus-visible ring everywhere.

## Acceptance criteria

1. `/requests/new` renders all four steps at 1440×900 and 390×844 with no horizontal scroll, no console errors.
2. Type choice drives step 2 fields; switching type clears stale field errors.
3. Continue blocked with visible reasons when required fields missing/invalid (per-family rules incl. due≥invoice, end≥start, VND integer amounts, net>0).
4. Vendor gross preview updates live; equals `net + vat` exactly (Decimal).
5. Documents step enforces the matrix; oversized/wrong-type upload shows inline alert; required-dot flips green when attached.
6. Review lists errors/warnings (duplicate hits) before submit; successful submit yields mono request number, Submitted confirmation, and one hash-chained AuditEvent whose chain verifies.
7. Submitting twice cannot double-submit (guard on lifecycle_state != DRAFT).
8. `uv run pytest tests/models tests/services` passes; `bash scripts/validate.sh` passes; new unit tests cover validators, money parsing, doc matrix, hash chain (incl. tamper detection), duplicate scan, submit guard.
9. E2E (`pytest -m e2e`) walks type→details→docs→review→submit happy path + a validation-failure path; asserts no browser errors at both viewports.

## Out of scope (tracked)

See `issues/05-persistence-and-controls.md`: durable SQL persistence/repositories, blob storage + malware scan + Azure DI, durable drafts, approval-route preview, queue/detail integration, auth identity. Each blocks release, not this feature's internal completeness.

## As-built amendments (2026-08-26, post-implementation)

Deviations discovered while building against Reflex 0.9.8.post1 — the pinned
contracts above remain the base; these extend them:

1. **State additions** (all rendered from, none removed): `status_message`
   (live-region copy for gate outcomes), plus cached computed vars
   `doc_rows`, `doc_keys`, `required_doc_keys`, `uploaded_keys`,
   `settleable_advances`, `field_issue_rows`, `error_fields`, `issue_count`.
   Reason: Var methods (`contains`) need plain list vars, and foreach/event
   scopes cannot carry dynamic dict keys.
2. **Vendor selects**: `payment_terms_code` / `payment_method_code` state vars
   and DraftCommand fields added; model requires both values, so the form asks
   instead of fabricating defaults.
3. **Select placeholders**: every select whose default is `""` renders a
   disabled `Select…` option — prevents silent first-option preselection.
4. **Documents step**: static slot checklist (9 known keys) conditioned on
   `doc_keys.contains(key)` instead of foreach over rows — foreach args cannot
   cross into event-handler payloads or f-string ids safely. Each row pairs a
   dropzone (`rx.upload`) with an explicit **Attach** button calling
   `handle_upload(rx.upload_files(upload_id=…))`; accept uses the MIME→ext dict
   form required by react-dropzone.
5. **Gate split**: step-2 Continue validates *field issues only*; document
   blockers surface at step 3 and Review. (Initial combined gate made the
   Documents step unreachable.)
6. **Numeric inputs**: `set_field(name, value: str | int | float)` normalizes
   number-widget floats (`10000000.0` → `"10000000"`) before Decimal parsing.
7. **submit_request** signature grew `trail: InMemoryAuditTrail` and
   `retention_policy_id: UUID = RETENTION_POLICY_ID_PROTOTYPE` kwargs so the
   session trail instance is injected, not global.
8. **Session objects** live in underscore-prefixed annotated attrs
   (`_session_trail`, `_submitted_model_store`) — Reflex forbids setattr of
   undeclared names and does not sync underscore vars to the client.
9. **Entry-point fix (pre-existing bug)**: `WisPay.py` listed stylesheet
   `token.css`, which does not exist; app could not compile at all. Pointed to
   the actual `design-tokens.css`. Note: uncommitted working-tree edits rename
   docs to `token.css` — if that rename is intended, rename the asset file too.
10. **Budget period default** is stamped (`YYYY-MM` of today) when a type is
    chosen, matching the source example's convenience without hiding the field.
