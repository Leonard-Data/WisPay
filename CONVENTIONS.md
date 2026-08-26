# WisPay coding conventions

Authoritative for all code in this repo. Domain terms and security invariants come from `WisPay-doc/CONTEXT.md`; this file covers how we write the code.

## Tooling

- **uv** manages the environment and dependencies (`uv.lock` is the source of truth).
- **ruff** lints and formats (replaces black/isort/flake8). Config in `pyproject.toml`.
- **mypy --strict** type-checks. Config in `pyproject.toml`. One deliberate concession: `warn_return_any = false`, because Reflex's component constructors (`rx.container`, `rx.vstack`, …) return `Any`; all other strict checks remain on.
- **pytest** runs tests. Config in `pyproject.toml`.
- Run everything: `bash scripts/validate.sh`.

## Python style

- Target Python 3.14. Max line length 100 (enforced by ruff).
- Type hints are **required** on all public functions and class attributes.
- Prefer stdlib + Pydantic over hand-rolled helpers.
- No `print` in committed code — use Reflex/logging.
- No secrets, tokens, or connection strings in source — `.env` only.

## Project layout

```text
WisPay/                 # application package (app_name = "WisPay")
  __init__.py
  WisPay.py             # app entrypoint (rx.App, page registration)
  components/           # reusable rx components (documented, page-agnostic)
  layout/               # page shells and structural wrappers (shell(), nav frame)
  models/               # Pydantic domain models (mirror CONTEXT.md terms)
  pages/                # page components: thin composition of components/
  services/             # Azure DI, Azure SQL, business logic (pure, testable)
states/                  # rx.State subclasses (one concern per file)
tests/                   # mirrors package layout; test_*.py
scripts/                 # tooling (validate.sh)
.scratch/                # feature specs (issues live on GitHub)
```

## Components

Components live in `WisPay/components/`; pages compose them and add only page-specific markup.

- **Placement**: a component a second page could use goes in `components/` — form fields, summary rows, status pills, cards, table shells. A helper used by one page stays in that page file; promote it the moment a second consumer appears.
- **Reusable by construction**: components take data and event handlers as arguments, pass `class_name` through to callers, and take visual values from `WisPay/styles.py` tokens. Page copy, routes, and state wiring stay in the page.
- **Documented**: every public component function has a docstring stating what it renders, its arguments, and one usage line; the module docstring names the component family it covers.
- **Readable**: one concept per component, names that say what renders (`invoice_status_pill`, not `widget2`), section comments in longer files.
- Pages stay thin: composition and layout only; business logic belongs in `services/`.

## Reflex conventions
- One `rx.State` concern per file in `states/`. State holds data; events mutate it.
- Use `rx.Var` for derived values; never compute in render functions.
- Event handlers return or yield `rx` events — no side effects outside handlers.
- Components are pure functions returning `rx.Component`. No business logic, no I/O.
- Prefer Radix Themes + Tailwind utility classes; follow `WisPay-doc/docs/product/DESIGN.md` tokens, not ad-hoc colors.
- Read the `reflex-docs` skill for current API shapes — do not rely on memory.

## Pydantic models

Before changing `WisPay/models/`, read the sibling `../WisPay-doc/CONTEXT.md`, canonical backend data model and lifecycle state machine, and ADR-0004/ADR-0006.

- Domain records and value objects subclass `WisPayBaseModel` (Pydantic v2). Use typed fields; do not substitute dataclasses, `TypedDict`, untyped dictionaries, or `Any` for domain models.
- Models are frozen and reject extra fields by default. Services produce a new validated model for a change and Reflex State replaces the whole value; domain records are not mutated in place.
- `models/` is pure domain code. It may import the standard library and Pydantic, but not Reflex, ORM/SQL drivers, Azure SDKs, environment configuration, repositories, or I/O clients.
- Models enforce structural invariants and pure calculations. Services own authorization, lifecycle guards, idempotency, audit emission, persistence, and side effects.
- Every monetary field uses `Money`, which stores `Decimal` amount, ISO currency code, and decimal scale. Floating-point amounts are prohibited; VND uses scale 0.
- Submitted records retain typed display snapshots for external user, beneficiary, bank, organization, and accounting references.
- Lifecycle code exposes exactly the 14 canonical states; `Overdue` is derived. Workflow instances and approval steps retain frozen rule versions, generation inputs, assignments, delegations, decisions, and timestamps.
- `AuditEvent` carries previous/event hash fields and reason metadata. `AuditService` owns canonical serialization, hash computation, verification, and transactional append behavior.
- Closed vocabularies use canonical `StrEnum` values. Administrator-configurable values such as payment methods remain validated strings or configuration references rather than hard-coded enums.
- Service commands, results, typed errors, and runtime user context live with the service layer unless a later ADR makes them canonical domain records.
- Export every canonical logical record through `WisPay.models.CANONICAL_RECORD_TYPES`. Model changes include mirrored `tests/models/` coverage and must pass the conformance test.

## Security & audit (mandatory)

From `CONTEXT.md` invariants — these gate every payment-related change:

- The requester can never approve their own request.
- Only an approved request may enter payment processing.
- Only authorized Finance users may record payment completion.
- Every state transition and decision is written to the audit log.
- No hard-deletes of financial records or audit events — use status/correction flows.
- Azure and SQL credentials come from env vars (`AZURE_*`), never literals.

## Testing

- Tests live in `tests/`, named `test_*.py`, mirroring the package.
- F.I.R.S.T.: Fast, Independent, Repeatable, Self-validating, Timely.
- Services and models get unit tests; workflows get integration tests covering normal, over-budget, exception, correction, and executive-approval paths (see delivery plan Phase 3 verify).
- No test skips without a tracked GitHub issue.

## Commits

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- `scripts/validate.sh` must pass locally before pushing. CI re-runs it.
- Never commit `.env`, `*.db`, or `assets/external/`.
