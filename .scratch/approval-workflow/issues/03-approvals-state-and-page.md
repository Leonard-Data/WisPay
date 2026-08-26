# 03 — Approvals state adapter, /approvals page, submission persistence seam

Status: claimed
Feature: `.scratch/approval-workflow/spec.md` (read first — contracts pinned there)

## Target

New files:
- `WisPay/services/runtime.py`
- `WisPay/states/__init__.py`
- `WisPay/states/approvals.py`
- `WisPay/pages/approvals.py`
- `tests/e2e/test_approvals.py`

Edits (only these):
- `WisPay/routers.py` — register `/approvals` between `/requests/new` and `/404`.
- `assets/layout.css` — append `.wispay-appr-*` section only.
- `WisPay/states/request_create.py` — submit() seam: after a successful service submit,
  persist via `runtime.stores().requests.save(...)` in try/except that degrades to a
  non-fatal warning message. Session behavior must be preserved when SQL is down.
- `components/sidebar.py` ONLY if an Approvals nav placeholder exists — wire its target;
  otherwise do not touch it and note the gap.

## Change

Implement spec §"State adapter + page + wiring": thin `rx.State` adapter per ADR-0005
(collect → call services → translate typed errors), `runtime.stores()` singleton that
connects lazily, runs `ensure_schema` once, caches `Stores`, and converts connection
failures into readable banner state (never crash the page).

Page follows AGENTS.md UI rules: start from Buridan UI (`https://buridan-ui.reflex.run/llms.txt`,
doc pages resolve by appending `.md`; link the chosen component pages in your notes);
`DESIGN.md` + `assets/token.css` govern everything; tokens via `WisPay/styles.py`; reuse
existing shell/layout; honest empty states; no fabricated metrics; copy distinguishes
recording decisions from moving money. Sections: header, pending-decisions table,
decision panel (reason textarea; Approve primary; Reject/Return require reason),
route timeline card, sample-actor switcher chip (labeled sample configuration).
Responsive 768px/560px breakpoints, focus-visible, aria-live on status changes,
44px touch targets. Class prefix `wispay-appr-*`.

## E2E

`tests/e2e/test_approvals.py`, marker `e2e`, following existing `tests/e2e/conftest.py`
patterns: wizard-submit a vendor request → open `/approvals` → generate route → approve as
Line Manager sample actor → assert outcome pill + timeline reflect decision. Guard path:
requester actor sees self-approval blocked (service guard surfaces as visible message).
Both viewports asserted by the review protocol (ticket 04 performs the live browser pass;
this file must run green against a locally started server with SQL reachable — if SQL is
unreachable at authoring time, still write it and leave execution to ticket 04 rather than
skipping).

## Acceptance

- `uv run pytest tests/models tests/services -q` still green (your edits don't break others).
- ruff/mypy clean; route appears in `routers.py`; no console errors from a compile check
  (`uv run reflex export --no-zip` or frontend build) if available quickly.
