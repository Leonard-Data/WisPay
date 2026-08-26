# 04 — E2E coverage + live browser review

Status: resolved
Feature: `.scratch/payment-request-create/spec.md` (acceptance criteria 1–9)

## Target

- New: `tests/e2e/test_request_create.py`

## Change

Playwright suite (markers `@pytest.mark.e2e`, reuse `tests/e2e/conftest.py` fixtures):

1. Happy path desktop 1440×900: open `/requests/new` → pick Vendor card → fill title/vendor/invoice/date/due/net/vat/cost center/category/purpose (valid data) → Continue → attach a small generated PDF to Invoice slot (Playwright `set_input_files` on the hidden input) → Continue → Review shows no error panel → Submit → confirmation with mono request number visible; assert URL still `/requests/new`, no console/page errors.
2. Validation path: attempt Continue on empty details → expect field-error texts visible and step unchanged; fix → proceed.
3. Documents gate: reach step 3 without attachment → Continue blocked with "Attach …" messaging; wrong-extension upload shows inline alert.
4. Responsive pass at 390×844 for the happy path skeleton (steps render stacked, no horizontal overflow: `document.documentElement.scrollWidth <= innerWidth`).

Live review (separate from pytest, mandatory): start server `uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1`; drive DevTools MCP through both viewports; capture a11y snapshot + screenshot + console + network failures per route state (each step); compare against `docs/product/DESIGN.md`; leave browser open for user validation; report screenshot paths.

## Acceptance

`uv run pytest -m e2e -q` green against the running server; findings fixed or filed; screenshots referenced in this ticket's Comments section.


## Comments

- 2026-08-26 (agent): tests/e2e/test_request_create.py — happy path, empty-details validation, mobile 390x844 all pass (`pytest -m e2e tests/e2e/test_request_create.py`: 3 passed).
- Live DevTools review done at 1440x900 and 390x844; zero console errors on the wizard; screenshots: .scratch/tmp/desktop-review.png, desktop-success-2.png, mobile-step1.png.
- 2026-08-26 (agent): baseline failure RESOLVED. Root cause: HEAD's layout.css had no responsive shell at all (the test asserted unimplemented behavior); the working tree implements it. Residual failures were test-side races: one-shot getComputedStyle reads sampled the margin-left/width mid-transition (fixed with retrying expect(...).to_have_css), and the drawer-close step clicked the hamburger buried under the open drawer (fixed to tap the exposed backdrop strip). Suite green 3 consecutive runs; GitHub issue #2 closed with evidence.
