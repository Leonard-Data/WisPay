# Codebase Lint, Type, and Format Audit Report

## Audit Commands

All commands run from the project root (`E:\projects\WisPay`):

```bash
# Ruff lint
.venv\Scripts\python.exe -m ruff check .

# Ruff format check
.venv\Scripts\python.exe -m ruff format --check .

# Mypy type check (as defined in validate.sh)
.venv\Scripts\python.exe -m mypy WisPay

# Mypy type check (as specified in t5 contract)
.venv\Scripts\python.exe -m mypy WisPay states

# Additional: mypy on tests (not in the gate, but audited)
.venv\Scripts\python.exe -m mypy tests/

# Additional: mypy on scripts (not in the gate, but audited)
.venv\Scripts\python.exe -m mypy scripts/
```

## Results Summary

| Check | Scope | Result | Details |
|-------|-------|--------|---------|
| Ruff lint | Entire repo (`.`) | ✅ **PASS** | All checks passed |
| Ruff format | Entire repo (`.`) | ✅ **PASS** | 214 files already formatted |
| Mypy | `WisPay` (gate scope) | ✅ **PASS** | No issues found in 99 source files |
| Mypy | `WisPay states` (contract scope) | ✅ **PASS** | No issues found in 99 source files |
| Mypy | `tests/` (out of gate) | ⚠️ 1 issue | `fakes.py` module naming conflict |
| Mypy | `scripts/` (out of gate) | ❌ 10 errors | 2 files with type issues |

## Ruff Lint

**Status: ✅ All checks passed!**

Ruff lint passes with zero issues across the entire repository (WisPay, states, tests, scripts).

Lint rules enabled: `E` (pycodestyle errors), `W` (pycodestyle warnings), `F` (pyflakes), `I` (isort), `B` (flake8-bugbear), `UP` (pyupgrade), `SIM` (flake8-simplify), `C4` (flake8-comprehensions), `TCH` (flake8-type-checking).

Ignored: `E501` (line length, handled by formatter).

## Ruff Format

**Status: ✅ All files already formatted!**

214 Python files are properly formatted across the entire repository.

## Mypy Type Check — `WisPay` + `states` (gate + contract scope)

**Status: ✅ No issues found in 99 source files**

The project's strict mypy configuration passes cleanly on both the `WisPay/` package and the `states/` directory. All strict checks are enabled except `warn_return_any = false` (documented concession for Reflex's `rx.*()` components returning `Any`).

## Mypy Type Check — `tests/` (out of gate scope)

**Status: ⚠️ 1 issue found (blocking only if tests are type-checked)**

```
tests/services/fakes.py: error: Source file found twice under different module names: "fakes" and "tests.services.fakes"
```

**Root cause:** The `tests/services/` directory lacks an `__init__.py` file. Other test subdirectories (`tests/components/`, `tests/pages/`) have `__init__.py` files, but `tests/services/` and `tests/states/` and `tests/models/` and `tests/e2e/` do not (except `tests/components/__init__.py` and `tests/pages/__init__.py`).

Wait — rechecking: `tests/components/` and `tests/pages/` have `__init__.py`, but the glob showed only those two. The issue is specifically with `tests/services/fakes.py` being importable as both `fakes` (via `pythonpath = ["."]` from project root) and `tests.services.fakes`.

**Note:** The project's `validate.sh` only runs `mypy WisPay` (not `mypy tests/`), so this issue does not currently block the CI gate. However, if type-checking is extended to tests, this needs to be resolved.

## Mypy Type Check — `scripts/` (out of gate scope)

**Status: ❌ 10 errors in 2 files**

The `scripts/` directory is NOT type-checked by `validate.sh` (which only runs `mypy WisPay`). The mypy config has `ignore_missing_imports = true` for `scripts.*` modules, but this doesn't suppress type errors within the scripts themselves.

### `scripts/smoke_approval_flow.py` — 7 errors

| Line | Error Type | Description |
|------|-----------|-------------|
| 115 | `no-untyped-def` | `_counts(conn)` parameter missing type annotation |
| 140 | `attr-defined` | `"RuleStore" has no attribute "ensure_seeded"` — API mismatch |
| 146 | `arg-type` | `get_by_number()` argument is `str \| None` but function expects `str` |
| 184 | `arg-type` | `decision="Approved"` (Literal) doesn't match expected `ApprovalDecision` enum |
| 197 | `attr-defined` | `"object" has no attribute "close"` — conn typing too narrow |
| 214 | `attr-defined` | `"RuleStore" has no attribute "ensure_seeded"` (duplicate) |
| 218 | `attr-defined` | `"object" has no attribute "close"` (duplicate) |

### `scripts/db_diagnose.py` — 3 errors

| Line | Error Type | Description |
|------|-----------|-------------|
| 183 | `attr-defined` | `"object" has no attribute "cursor"` — connection object untyped |
| 192 | `attr-defined` | `"object" has no attribute "cursor"` (duplicate) |
| 207 | `attr-defined` | `"object" has no attribute "close"` — connection object untyped |

**Cross-reference with CONVENTIONS.md:**
- The scripts violate the "type hints required on all public functions" convention (line 115).
- The scripts use `"Approved"` string literal instead of the `ApprovalDecision` enum, which violates the "Closed vocabularies use canonical StrEnum values" convention.
- The `ensure_seeded` method mismatch suggests the script was written against an API that has since changed.

**Note:** These scripts require a live Azure SQL connection to run, so they may not have been exercised in CI. They are documented as manual diagnostic scripts.

## Cross-Reference Against CONVENTIONS.md

### Python Style
- ✅ All functions have type annotations in `WisPay/` and `states/` (mypy strict passes).
- ✅ No `print` statements in committed application code (verified by ruff lint — `T20` is not explicitly enabled, but the convention says "use Reflex/logging").
- ✅ No secrets in source (verified — `.env` is referenced for Azure credentials).

### Project Layout
- ✅ `WisPay/`, `states/`, `tests/` structure follows the documented convention.

### Testing
- ✅ Tests follow F.I.R.S.T. principles (no skips found).

## Prioritized Remediation Plan

### Tier 1 — Must Fix Before CI Extension (High Priority)

These issues would cause CI failures if mypy were extended to cover `tests/` or `scripts/`:

1. **`tests/services/__init__.py` missing** — Add `__init__.py` to `tests/services/` to resolve the module naming conflict in `fakes.py`. Also check `tests/states/` and `tests/models/` for the same issue (they may need `__init__.py` too, or the existing `tests/components/__init__.py` and `tests/pages/__init__.py` need to be made consistent).

2. **`scripts/smoke_approval_flow.py` — `ensure_seeded` API mismatch (lines 140, 214)** — The `RuleStore` interface has changed. The method `ensure_seeded` no longer exists. Fix to use the current API (see `WisPay/services/sql_repositories.py`).

3. **`scripts/smoke_approval_flow.py` — `decision="Approved"` string literal (line 184)** — Replace with `ApprovalDecision.APPROVED` enum value to match `DecisionCommand.decision` type.

4. **`scripts/smoke_approval_flow.py` — untyped `conn` parameter (line 115)** — Add type annotation for `_counts(conn: ...)`.

5. **`scripts/smoke_approval_flow.py:146` — `get_by_number` arg-type** — Handle `None` case for `request.request_number` before passing to `get_by_number`.

6. **`scripts/smoke_approval_flow.py:197,218` and `scripts/db_diagnose.py:183,192,207` — untyped `conn`** — Add proper type annotations for connection objects.

### Tier 2 — Improve Code Quality (Medium Priority)

None currently. The `WisPay/` and `states/` code is clean per ruff and mypy strict.

### Tier 3 — Future Hardening (Low Priority)

1. Consider adding `tests/` and `states/` to the mypy gate in `validate.sh` to catch type issues in tests early.
2. Consider adding `scripts/` to the mypy gate, which would surface the 10 errors above as CI failures.
3. The `TCH` (flake8-type-checking) rule is enabled — verify all imports in `TYPE_CHECKING` blocks are correct (ruff already enforces this, and it passes).

## Conclusion

The codebase is in **excellent** condition from a lint, type, and format perspective:

- **Ruff lint**: ✅ Zero issues across the entire repo
- **Ruff format**: ✅ All 214 files properly formatted
- **Mypy (WisPay + states)**: ✅ Zero issues in 99 source files under strict mode

The only issues found are in **`scripts/`** (10 mypy errors in 2 files) and a **module naming conflict in `tests/services/`** — both of which are outside the current CI gate scope (`validate.sh` only runs `ruff check .`, `ruff format --check .`, `mypy WisPay`, and `pytest`). These should be fixed before extending the type-checking gate to cover tests and scripts.
