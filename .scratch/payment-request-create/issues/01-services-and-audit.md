# 01 — Creation services + session audit trail

Status: resolved
Feature: `.scratch/payment-request-create/spec.md` (read it first — contracts are pinned there)

## Target

New files only:
- `WisPay/services/__init__.py`
- `WisPay/services/reference_data.py`
- `WisPay/services/request_creation.py`
- `WisPay/services/audit_trail.py`
- `tests/services/test_reference_data.py`
- `tests/services/test_request_creation.py`
- `tests/services/test_audit_trail.py`

Do NOT touch: `states/*`, `WisPay/pages/*`, `routers.py`, `assets/*`, `WisPay/styles.py`, anything under `WisPay/models/`.

## Change

Implement exactly the signatures in the spec's "Service layer" contract block.

Hard rules:
- Pure Python + Pydantic + `WisPay.models.*` imports only. **No `reflex` import anywhere.** No I/O except checksumming bytes passed in. All datetimes timezone-aware.
- Models are `frozen=True, extra="forbid"` — construct them fully; never mutate.
- `ruff` clean (line length 100), `mypy --strict` clean, no `print`.
- Money: parse from decimal strings only; VND scale 0, USD/EUR scale 2; reject >scale fractional input with a user-safe message before hitting `Money` where practical.
- `build_payment_request` maps `DraftCommand` → full `PaymentRequest` DRAFT aggregate: derive `duplicate_warning_key` = f"{beneficiary}|{invoice_number}|{gross}" (vendor), `accounting_period` = "YYYY-MM" from invoice/expense date, beneficiary `BeneficiaryReference(beneficiary_type=…, display_name=…, captured_at=now)`, full `AccountingDimension` from sample refs, `lifecycle_version="v1"`, `request_id=uuid4()`.
- `submit_request`: guard `lifecycle_state is DRAFT` else typed `ValueError("only draft requests can be submitted")`; set `request_number` ("WPR-YYYY-nnnn", injected via `request_number` arg) + `submitted_version=1`; transition to `SUBMITTED` via `.evolve()`; build one `AuditEvent` (action `Submitted`, canonical JSON of the submitted record as `new_value`, chain hash from trail).
- `audit_trail.InMemoryAuditTrail`: append-only, genesis `"0"*64`, `canonical_payload` = key-sorted compact JSON, `chain_hash` = sha256(previous_hash + payload).hexdigest; `verify()` recomputes chain and returns False on any mismatch/tamper.
- `doc_requirements` implements the spec's provisional matrix keyed by family/subtype strings used by the wizard ("vendor"/"standard", "employee"/"reimbursement"|"advance"|"settlement"| "internal").
- `duplicate_scan`: match same beneficiary display_name (casefold) + invoice_number among vendor records; return warning strings.
- `validate_draft_command`: field-keyed issues using the same field names as the pinned state vars (`title`, `net_text`, `due_date`, …); blocking messages for cross-field rules (due≥invoice, end≥start, net>0, settlement requires linked advance id, required docs presence check takes a mapping param — accept `uploads_by_key: Mapping[str, int]` counts argument here OR keep doc checks at review step; choose: add parameter `uploaded_keys: frozenset[str]` defaulting to empty and emit blocking "Attach <label>." entries).

## Tests (F.I.R.S.T., no skips)

Cover at minimum: money parse happy/sad (VND decimal rejection, wrong scale, negative), gross addition, validate_draft_command per-family required fields + cross-field order rules + doc-blocking, build→submit round trip producing valid SUBMITTED aggregate with matching totals (model validators pass), double-submit guard raises, duplicate scan hit/miss, hash chain determinism + tamper detection (mutate an event → verify False), doc matrix shape per subtype.

## Acceptance

`uv run pytest tests/services -q` green; `uv run mypy WisPay/services tests/services` clean; `uv run ruff check WisPay/services tests/services` clean. Report exact command outputs.


## Comments

- 2026-08-26 (agent): implemented + 38 unit tests green (`pytest tests/services -q`).
- `submit_request` grew `trail` and `retention_policy_id` kwargs (see spec amendments 7).
- `DraftCommand` gained `payment_terms_code` / `payment_method_code`; validation enforces them for vendor.
