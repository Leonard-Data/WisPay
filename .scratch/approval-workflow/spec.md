# Spec — Approval workflow tracking (approvals, services, states)

Status: ready-for-agent · Created: 2026-08-26 · Owner: agent (this iteration) · Branch: `feature/approval`

## Sources read (ground truth)

- `E:/projects/WisPay-doc/CONTEXT.md` — terminology (Approval Route, Approval Step, Workflow Instance, Approver), unified lifecycle, core invariants 1–10.
- `E:/projects/WisPay-doc/docs/reference/backend/lifecycle-state-machine.md` — states, `Approval Pending → Approved` guard ("all required approval steps approved"), exception transitions, route snapshots, edit-invalidation rules, guard ownership (workflow service validates decisions).
- `E:/projects/WisPay-doc/docs/reference/backend/data-model.md` — `WorkflowInstance`, `ApprovalStep`, versioning rule ("workflow rules … are versioned or snapshotted").
- `E:/projects/WisPay-doc/docs/reference/backend/service-layer.md` — `WorkflowService` + `ApprovalService` ownership, standard write shape, Reflex State adapter rules.
- `E:/projects/WisPay-doc/docs/adr/0005-service-reflex-state-seam.md`, `0006-versioned-lifecycle-state-machine.md`.
- App repo: `CONVENTIONS.md`, `AGENTS.md` security invariants, existing `WisPay/models/workflow.py` (ApprovalStep/WorkflowInstance already modeled), `models/lifecycle.py`, `services/request_creation.py`, `services/audit_trail.py`, `routers.py`.
- Prior feature: `.scratch/payment-request-create/spec.md` (session-scoped precedent: prototype requester, InMemoryAuditTrail).

## Problem

Requests can be submitted but never reach approval: no route generation, no decision recording, no tracking surface. The lifecycle halts at `Submitted`. This feature implements the approval slice end-to-end:

1. **Services** — versioned DB-backed route generation (`WorkflowService`) + guarded decisions (`ApprovalService`), pure Python per ADR-0005.
2. **States** — thin Reflex adapters that call the services.
3. **Tracking UI** — `/approvals` page: pending-approval queue, decision actions, route timeline.
4. **Persistence** — Azure SQL now: requests, workflow instances/steps, audit events, and versioned workflow rules survive sessions (user-selected scope; replaces the payment-request-create spec's deferred issue 05 for these tables only).

## Decisions

1. **DB-backed versioned rules (user decision):** rule rows live in `dbo.wispay_workflow_rule`, loaded by rule version; `WorkflowInstance.generation_inputs` + `workflow_rule_version` freeze the route forever (ADR-0006: later rule changes never rewrite snapshots). Seed set `v1` ships as idempotent seed rows labeled *sample configuration*.
2. **Azure SQL persistence for this slice's aggregates only (user decision):** payment requests, workflow instances (+steps), audit events, rules. Documents/Azure DI/blob storage remain out of scope.
3. **Route generation** happens on demand when an operator opens `/approvals` for a `Submitted` request whose latest instance is absent — MVP trigger instead of the full Evidence Validation pipeline (out of scope). Guard: only `Submitted` requests can get a route; generation emits an audit event.
4. **Decision guards enforce invariant 3 in the service**, not the UI: requester can never decide their own request; only the snapshotted step approver may act; reject/return require a reason; only the earliest pending sequence (or its parallel group) is actionable; decided routes are closed.
5. **Outcomes:** all required steps approved → `final_outcome=Approved` + `route_completed=True`; any rejection → `final_outcome=Rejected`; returned → `final_outcome=Returned`, pending future steps left untouched (snapshot preserved). Lifecycle transitions themselves (`Approval Pending → Approved/Rejected/Returned for Correction`) remain a LifecycleService concern — this slice stops at the route outcome + audit evidence; state pages display outcomes.
6. **Delegation deferred:** `ApprovalDecision.DELEGATED` and `Delegated` resolution land in a tracked follow-up; this iteration pins single-approver decisions.
7. **Identity stays prototype (decision 10 of prior spec):** sample actors from `reference_data.py` — distinct requester vs approver snapshots so separation-of-duties is real at the guard level. Actor switcher is a visible sample control on `/approvals` (labeled sample configuration).
8. **Audit durability:** hash-chain logic stays in `audit_trail.py` (`canonical_payload`, `chain_hash`); new durable trail reads `last_event_hash()` from SQL and appends. Session `InMemoryAuditTrail` unchanged.
9. **Resubmission:** a `Returned for Correction` → resubmit flow regenerates a *new* workflow instance (old snapshot untouched). Correction round-trip UI is out of scope; service supports it.
10. **No fabricated metrics/copy:** empty queue renders the honest empty state (DESIGN.md voice); all sample data visibly labeled.

## Contracts (pinned for parallel work — implement exactly)

### Store protocols + SQL infra — ticket 01 owns

`WisPay/services/db.py`:

```python
def connection_string() -> str          # AZURE_SQL_* env; driver default "ODBC Driver 18 for SQL Server"
def connect() -> pyodbc.Connection      # parses env each call; raises RuntimeError with setup hint on failure
def ensure_schema(conn: pyodbc.Connection) -> None   # idempotent CREATE TABLE IF OBJECT_ID(...) IS NULL + seed rules v1
```

`WisPay/services/repositories.py`:

```python
class RequestStore(Protocol):
    def save(self, request: PaymentRequest) -> None            # upsert by request_id
    def get(self, request_id: UUID) -> PaymentRequest | None
    def get_by_number(self, request_number: str) -> PaymentRequest | None

class WorkflowStore(Protocol):
    def save_instance(self, instance: WorkflowInstance) -> None # upsert incl. step rows
    def get_instance(self, workflow_instance_id: UUID) -> WorkflowInstance | None
    def latest_instance_for_request(self, request_id: UUID) -> WorkflowInstance | None
    def pending_instances(self) -> tuple[WorkflowInstance, ...]  # final_outcome == Pending, newest first

class AuditEventStore(Protocol):
    def last_event_hash(self) -> str                            # GENESIS_HASH when empty
    def append(self, event: AuditEvent) -> None
    def events_for_request(self, correlation_id: str) -> tuple[AuditEvent, ...]

class RuleStore(Protocol):
    def active_version(self) -> str
    def rules(self, version: str) -> tuple[WorkflowRule, ...]

@dataclass(frozen=True, slots=True)
class Stores:  # bundle handed to callers
    requests: RequestStore
    workflows: WorkflowStore
    audit: AuditEventStore
    rules: RuleStore
```

`WisPay/services/sql_repositories.py`: SQL implementations of all four (payload columns serialize with `model_dump_json`, parse with `model_validate_json`), plus:

```python
def sql_stores(conn: pyodbc.Connection) -> Stores
class DurableAuditTrail:   # same append signature as InMemoryAuditTrail but chains over store.last_event_hash()
```

`tests/services/fakes.py`: in-memory doubles of the four protocols (`FakeStores` bundle) — no skips, no SQL needed for unit tests.

Schema `scripts/sql/schema.sql` (mirrored by `ensure_schema`, prefix `dbo.wispay_*`):

| Table | Key columns |
| --- | --- |
| `wispay_payment_request` | `request_id` PK, `request_number` UNIQUE, `lifecycle_state`, `payload NVARCHAR(MAX)`, `created_at/updated_at DATETIMEOFFSET` |
| `wispay_workflow_instance` | `workflow_instance_id` PK, `request_id` idx, `rule_version`, `outcome`, `current_step_sequence`, `generated_at`, `payload NVARCHAR(MAX)` |
| `wispay_workflow_rule` | `rule_id INT IDENTITY` PK, `UNIQUE(version,priority,step_sequence,approver_user_id)`, filter + step columns |
| `wispay_audit_event` | `event_id` PK, `entity_type/entity_id/action`, `correlation_id` idx, `previous_hash/event_hash CHAR(64)`, `new_value`, `reason`, `occurred_at/recorded_at` |

Rules: repositories import stdlib + pyodbc + `WisPay.models` + `audit_trail` helpers only. No Reflex. Parameterized queries only (no string interpolation of values).

### Workflow rules + services — ticket 02 owns

`WisPay/services/workflow_rules.py`:

```python
@dataclass(frozen=True, slots=True)
class WorkflowRule:
    version: str; priority: int                  # lower priority matches first
    request_type: RequestType | None             # None = any
    min_amount: Decimal | None; currency_code: str | None
    legal_entity_code: str | None; department_code: str | None
    project_code: str | None; risk_flag: str | None
    step_sequence: int; parallel_group: str | None
    approver_role: RoleName; approver_user: UserSnapshot
    due_days: int | None

SEED_RULE_VERSION: str                          # "v1"
SAMPLE_APPROVER_LINE_MANAGER / SAMPLE_APPROVER_EXECUTIVE / SAMPLE_REQUESTER_PROTOTYPE: UserSnapshot
THRESHOLDS_V1: Mapping[str, Decimal]            # {"VND": 100000000, "USD": 10000, "EUR": 10000}
def seed_rules_v1() -> tuple[WorkflowRule, ...] # LM always; Executive when amount ≥ threshold in request currency
def matching_rules(rules, inputs: RouteGenerationInput) -> tuple[WorkflowRule, ...]
```

`WisPay/services/approval_workflow.py`:

```python
class GenerateRouteCommand(WisPayBaseModel):
    request_id: UUID
    generation_inputs: RouteGenerationInput

class DecisionCommand(WisPayBaseModel):
    workflow_instance_id: UUID; step_id: UUID
    decision: Literal[ApprovalDecision.APPROVED, ApprovalDecision.REJECTED, ApprovalDecision.RETURNED]
    actor: UserSnapshot
    reason: str | None = None
    comments: tuple[str, ...] = ()

class ApprovalWorkflowError(ValueError); ...   # NoRouteError, RouteClosedError, NotCurrentStepError,
                                               # SelfApprovalError, UnauthorizedApproverError, MissingReasonError, UnknownStepError

@dataclass(frozen=True, slots=True)
class RouteResult:     instance: WorkflowInstance; audit_events: tuple[AuditEvent, ...]
@dataclass(frozen=True, slots=True)
class DecisionResult:  instance: WorkflowInstance; route_completed: bool; audit_events: tuple[AuditEvent, ...]

def generate_route(cmd, *, rules: Sequence[WorkflowRule], rule_version: str, now: datetime) -> RouteResult
def decide(cmd, *, instance: WorkflowInstance, requester_id: UUID, now: datetime,
           trail_appender: Callable[[AuditEvent], None]) -> DecisionResult
```

Guard order in `decide`: route open → step known → step pending & actionable (earliest pending sequence or same parallel_group) → not self-approval → actor is step approver → reason required on Reject/Return. Each decision mutates the copied step (frozen model rebuild), recomputes `current_step_sequence` + `final_outcome`, and emits exactly one `AuditEvent` (action `Approved/Rejected/Returned`, `entity_type="approval_step"`, `correlation_id=request_id`) appended through `trail_appender` — the caller passes the durable/in-memory boundary. Pure domain: no Reflex, no pyodbc, no env access; timezone-aware datetimes; `Money` comparisons via shared-currency `Decimal` only.

### State adapter + page + wiring — ticket 03 owns

`WisPay/states/approvals.py` (thin adapter per ADR-0005):

```python
class approvals_state(rx.State):
    queue_rows: list[dict]        # {instance_id, step_id, request_number, title, amount_display, requester_name, approver_role, due_display}
    timeline_rows: list[dict]     # {sequence, approver_name, approver_role, decision, decided_display, is_current}
    selected_key: str             # "{instance_id}:{step_id}" or ""
    reason_text: str
    status_message: str
    actor_name: str               # current sample actor display name
    def load_queue(self) -> None              # ensure_schema-free read; surfaces readable errors in status_message
    def select_row(self, key: str) -> None
    def set_reason(self, value: str) -> None
    def decide(self, decision: str) -> None   # "Approved" | "Rejected" | "Returned"; reloads queue + timeline
    def switch_actor(self, name: str) -> None # cycles sample actors (labeled sample control)
    def generate_route_for(self, request_id: str) -> None  # MVP route trigger for Submitted requests without one
```

Server-side singleton accessor `WisPay/services/runtime.py::stores() -> Stores` (ticket 03 owns): lazily connects, `ensure_schema`, caches; converts connection failures into a readable banner state, never crashes the page.

Page `WisPay/pages/approvals.py` route `/approvals` registered in `routers.py` between `/requests/new` and `/404`: header (eyebrow `Approval tracking`, H1 `Approvals`), pending-decisions table card, decision panel (reason textarea; Approve primary; Reject / Return secondary with required-reason validation), route timeline card, sample-actor switcher chip, honest empty state. Class prefix `wispay-appr-*`, tokens only from `assets/token.css` via `styles.py`. Sidebar: wire the existing Approvals nav entry if a placeholder exists; otherwise leave navigation via direct URL and note it.

Seam edit (ticket 03 only): `states/request_create.py::submit()` additionally persists the submitted aggregate through `runtime.stores().requests.save(...)` inside try/except that degrades to a warning message (submission itself must not fail when SQL is down — session behavior preserved).

### E2E + browser review — ticket 04 owns

`tests/e2e/test_approvals.py`: happy path — submit a vendor request through the wizard, open `/approvals`, generate route, approve as Line Manager, assert outcome pill and audit-backed timeline; plus rejected-path guard assertion (requester actor cannot approve own request — service-level unit test in 02 covers the guard; e2e asserts the UI reflects it). Desktop 1440×900 + mobile 390×844 per AGENTS.md review protocol.

## Files (ownership map — no overlaps)

| Ticket | New files | Edits |
| --- | --- | --- |
| 01 | `WisPay/services/db.py`, `repositories.py`, `sql_repositories.py`, `scripts/sql/schema.sql`, `tests/services/fakes.py`, `tests/services/test_db.py`, `test_sql_repositories.py` | — |
| 02 | `WisPay/services/workflow_rules.py`, `approval_workflow.py`, `tests/services/test_workflow_rules.py`, `test_approval_workflow.py` | — |
| 03 | `WisPay/services/runtime.py`, `WisPay/states/__init__.py`?, `states/approvals.py`, `pages/approvals.py`, `tests/e2e/test_approvals.py` | `routers.py`, `assets/layout.css` (append), `states/request_create.py` (submit seam), optional `components/sidebar.py` nav label |
| 04 | — | runs suite + browser review; records findings |

## Acceptance criteria

1. `uv run pytest tests/models tests/services` green; `bash scripts/validate.sh` passes clean.
2. Service guards proven by unit tests: self-approval blocked, wrong approver blocked, non-current step blocked, missing reason blocked, closed route blocked, completion flips outcome + emits one audit event per decision, hash chain verifies across session boundary (durable trail over fakes).
3. Live Azure SQL smoke: `ensure_schema` creates tables idempotently; a scripted round trip (save request → generate route → persist → decide → re-read) survives a fresh connection; second run changes nothing structurally.
4. `/approvals` at both viewports: queue lists persisted pending steps, decision actions work end-to-end against real SQL, errors surface as banners, empty state honest.
5. Every decision visible in `/approvals` timeline matches `wispay_audit_event` rows (spot-checked via query in smoke).
