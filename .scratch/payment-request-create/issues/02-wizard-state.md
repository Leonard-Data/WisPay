# 02 — Wizard state adapter

Status: resolved
Feature: `.scratch/payment-request-create/spec.md` (pinned State API contract)

## Target

- New: `states/request_create.py`
- Edit allowed: `states/__init__.py` (export)

Do NOT touch: `WisPay/services/*` (import them), `WisPay/pages/*`, `routers.py`, `assets/*`, tests outside your scope.

## Change

Implement `RequestCreateState(rx.State)` exactly as pinned in spec §Contracts-State: every var listed, every handler listed. Rules (ADR-0005):

- Thin adapter: collect → call service → translate errors. No business rules in state beyond whitelisting and calling services.
- `set_field(name, value)`: whitelist the pinned field names; ignore unknown; after `net_text`/`vat_text`/`currency` changes call service `gross_of(parse_money(...))` inside try/except and store formatted string in `gross_preview` (empty on parse failure).
- `handle_upload(files: list[rx.UploadFile])`: async handler; validate extension (pdf/png/jpg/jpeg/xlsx case-insensitive) and ≤10 MB; compute sha256 while streaming bytes; append metadata dicts `{key, file_name, size_bytes, sha256_hex}` where `key` = first unmet slot from service `doc_requirements(family, subtype)` not already uploaded; wrong type/size → `upload_errors[key]` user-safe message; never store raw bytes in state.
- `go_next()` gates: step 1 requires family chosen (else toast-style message var); step 2 calls `validate_draft_command` with current inputs and stores `field_errors`/`blocking` (abort advance when field_issues non-empty); step 3 computes required slots vs uploads (blocking entries when unmet); success increments step.
- `submit()`: re-validate fully; call `build_payment_request` (catch pydantic ValidationError → map loc[0] to field_errors, abort); then `submit_request` with next number from internal counter `WPR-<current_year>-<seq:04d>`; append returned audit event into an `InMemoryAuditTrail` instance kept as class-level runtime object (module-scoped singleton is acceptable for session scope); push summary dict into `submitted_requests`; set `submitted_number`; leave prior steps intact for reset.
- Double-submit protection: if `submitted_number` non-empty, no-op.
- `reset_wizard()`: restore pristine defaults (step 1, empty fields, cleared errors/uploads/result).
- Verify Reflex 0.9.x APIs against the installed package (`.venv`) — e.g. `uv run python -c "import reflex as rx, inspect; print(inspect.signature(rx.upload_files))"` — instead of guessing; upload handler must match installed signature.

## Acceptance

`uv run python -c "from states.request_create import RequestCreateState"` succeeds; `uv run mypy states/request_create.py` clean (strict concessions already configured project-wide); `uv run ruff check states`. Handlers contain zero business-rule branching beyond gate sequencing. Report command outputs.


## Comments

- 2026-08-26 (agent): implemented; state imports clean, handlers verified in live browser flow.
- Added cached computed vars (doc_keys, required_doc_keys, error_fields, settleable_advances, field_issue_rows, issue_count) — see spec amendments 1/5.
- Backend-only session objects use underscore-prefixed annotated attrs per Reflex rules (spec amendment 8).
