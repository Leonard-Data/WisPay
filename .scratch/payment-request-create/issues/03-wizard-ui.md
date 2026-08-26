# 03 — Create page UI (wizard) + route + CSS

Status: resolved
Feature: `.scratch/payment-request-create/spec.md` (IA, per-step content, visual contract)
Source example (visual truth): `E:/projects/WisPay-deisgn/new-request.html` — copy its step markup semantics, class shapes, responsive rules into `wispay-new-*` classes.

## Target

- New: `WisPay/pages/request_new.py`
- Edits: `WisPay/pages/__init__.py` (export `request_new_page`), `routers.py` (Route between `/requests` and `/404`; title "New Payment Request · WisPay"), `assets/layout.css` (append a clearly-commented `wispay-new-*` section), `WisPay/styles.py` (append wizard values/namespaces only if needed; reuse `Tokens`/`Animations`/`Classes` first).

Do NOT touch: `states/request_create.py`, `WisPay/services/*`.

## Change

Build the four-step wizard consuming `RequestCreateState` exactly as pinned (state vars/handlers exist per contract even if implemented in parallel — code strictly against that API):

1. Header (eyebrow/H1/lede/Draft pill), step bar (buttons w/ `aria-current="step"`, disabled future, done clickable back), panels, sticky action bar (Back ghost / Continue primary / Submit primary on step 4), success panel replacing wizard when `submitted_number` non-empty (mono number, Submitted status pill, link to `/requests`).
2. Step 1 type cards per spec (groups, selected warm surface + inset ring, aria-pressed, Selected/Choose chip).
3. Step 2 dynamic sections per spec: Request / Accounting & amount / Business purpose; conditional blocks via `rx.cond(family == "vendor", …)` etc.; every label carries Required/Optional mono tag; errors adjacent with `aria-invalid`/`aria-describedby`; gross preview card `aria-live="polite"` bound to `gross_preview`; date inputs `type="date"`; amount inputs `inputmode="decimal"`.
4. Step 3 checklist rows bound to service matrix mirrored through state (`uploads`, `upload_errors`); hidden file input + visible secondary button; Attached pill + Remove; accepted-types note card.
5. Step 4 error panel (role=alert, count lead, jump buttons) + warning panel + summary rows + submission note (voice: approves and records, never moves money; corrections via Return-for-correction).
6. CSS: port source example styles onto tokens (`--ws-*` via existing token.css bridge); breakpoints 768px/560px as in source; reduced-motion guards; ≥44px targets; focus-visible ring preserved.
7. A11y: `aria-live` region announcing step changes; focus step heading on navigation (`id="wizard-step-title"`, tabindex=-1 trigger on step change); labels tied with htmlFor/id.

Follow existing page conventions (`requests_page` structure, shell() wrapper, class naming style in `assets/layout.css`). Read those files first.

## Acceptance

- `uv run python -c "from WisPay.pages.request_new import request_new_page; from WisPay.routers import ROUTES; assert any(r.route=='/requests/new' for r in ROUTES)"` passes.
- `uv run mypy WisPay/pages/request_new.py WisPay/routers.py` clean; `uv run ruff check WisPay/pages routers.py assets/../..WisPay/styles.py` clean (adjust to real paths).
- No hardcoded hex colors/sizes where a `--ws-*` token exists; no second styling system.
- List every state var/handler consumed; flag any contract mismatch found instead of working around it.


## Comments

- 2026-08-26 (agent): implemented four-step wizard, route `/requests/new`, wispay-new-* CSS appended to assets/layout.css reusing existing wispay-button system.
- Documents rows are static slots conditioned on doc_keys with explicit Attach buttons (spec amendments 1/4).
- Known gap: programmatic focus of step heading not wired; aria-live status region covers announcements instead.
