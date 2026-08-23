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
  state/                # rx.State subclasses (one concern per file)
  models/               # Pydantic domain models (mirror CONTEXT.md terms)
  components/           # reusable rx components
  pages/                # page components
  services/             # Azure DI, Azure SQL, business logic (pure, testable)
tests/                  # mirrors package layout; test_*.py
scripts/                # tooling (validate.sh)
.scratch/               # local issue tracker
```

Keep business logic **out** of components and pages — put it in `services/` so it is unit-testable.

## Reflex conventions

- One `rx.State` concern per file in `state/`. State holds data; events mutate it.
- Use `rx.Var` for derived values; never compute in render functions.
- Event handlers return or yield `rx` events — no side effects outside handlers.
- Components are pure functions returning `rx.Component`. No business logic, no I/O.
- Prefer Radix Themes + Tailwind utility classes; follow `WisPay-doc/docs/product/DESIGN.md` tokens, not ad-hoc colors.
- Read the `reflex-docs` skill for current API shapes — do not rely on memory.

## Pydantic models

- Domain models mirror terminology in `WisPay-doc/CONTEXT.md` exactly (Payment Request, Beneficiary, Approval Route, Payment Record, etc.).
- Validate at boundaries; models are the contract between layers.
- Use `ConfigDict(frozen=True)` for value objects that must not mutate.

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
- No test skips without a tracked issue in `.scratch/`.

## Commits

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- `scripts/validate.sh` must pass locally before pushing. CI re-runs it.
- Never commit `.env`, `*.db`, or `assets/external/`.
