# WisPay — application repo

WisPay is the internal portal for **Vendor and Employee Payment Requests**: submission through approval and Finance's recording of external payment completion.
This repo holds the working **Reflex** application. WisPay-doc remains the source of truth for domain, architecture, and product decisions; this repo's `DESIGN.md` is the checked-in visual implementation contract for the app.

## Source of truth

The canonical domain glossary, delivery plan, product documentation, and ADRs live in the sibling **WisPay-doc** repo (`../WisPay-doc`; currently `E:\projects\WisPay-doc`). Read these **before** writing feature code:

- `CONTEXT.md` — canonical domain glossary and invariants (actors, request categories, lifecycle, security invariants). Do not invent conflicting terminology.
- `wispay-delivery-plan.md` — phased delivery plan and release gates.
- `docs/product/DESIGN.md` — product-level design intent and context.
- `docs/product/APP-SETUP.md` — scaffold guide, DB schema, Azure Document Intelligence integration.
- `docs/adr/` — architecture decision records. Surface conflicts; don't silently override.

The app's visual implementation contract is the checked-in [`DESIGN.md`](DESIGN.md), synchronized from `E:\projects\WisPay-Design-System\DESIGN.md`. Use [`assets/token.css`](assets/token.css) for source-derived visual tokens. Domain terminology, workflow invariants, security rules, and architecture remain governed by WisPay-doc.

Two-repo boundary:

| Repo        | Contents                            | Stack                                                              |
| ----------- | ----------------------------------- | ------------------------------------------------------------------ |
| WisPay-doc  | Docs, glossary, plan, ADRs, design  | Astro, TypeScript, Markdown                                        |
| **WisPay**  | Working payment-request portal      | Reflex 0.9.8 (Python 3.14), Pydantic, Azure Document Intelligence, Azure SQL |

## Tech stack

- Python 3.14, managed with **uv** (`uv.lock`).
- Reflex 0.9.8 (Radix Themes + Tailwind v4, accent `red`).
- Pydantic v2 for domain models and validation.
- Azure Document Intelligence for document understanding; Azure SQL for storage.

## Quick start

```bash
uv sync --group dev          # install runtime + dev tooling (ruff, mypy, pytest, pre-commit)
uv run pre-commit install    # one-time: wire git hooks
uv run reflex run            # start the dev server
```

Copy `.env.example` to `.env` and fill Azure credentials before running anything that touches Document Intelligence or SQL.

## How we work — read first

- [`DESIGN.md`](DESIGN.md) — mandatory visual and interaction contract for any UI work.
- [`assets/token.css`](assets/token.css) — source-derived tokens; do not add ad-hoc design values.
- [`CONVENTIONS.md`](CONVENTIONS.md) — coding rules (style, Reflex patterns, Pydantic, security/audit invariants, testing).
- [`scripts/validate.sh`](scripts/validate.sh) — the pre-validation gate (lint + format + types + tests). **Must pass before any commit/push.**
- [`.pre-commit-config.yaml`](.pre-commit-config.yaml) — git hooks (ruff on commit, full gate on push).
- GitHub Issues — the issue tracker for this repo (manage with `gh`). Feature specs live under `.scratch/<feature-slug>/spec.md`.

## Security & audit invariants (from CONTEXT.md)

Non-negotiable for any payment-related change:

1. The requester cannot approve their own request.
2. Only an approved request can enter payment processing.
3. Only authorized Finance users can record payment completion.
4. Every submission, review, approval, rejection, change, delegation, and payment update is audit logged.
5. Submitted financial records and audit events are never hard-deleted.
6. Secrets (Azure keys, SQL passwords) live in `.env` only — never in code or commits.

## Domain model source rules

For every change under `WisPay/models/`:

1. Read `../WisPay-doc/CONTEXT.md`, `docs/reference/backend/data-model.md`, `docs/reference/backend/lifecycle-state-machine.md`, ADR-0004, and ADR-0006 before coding. Read the service-layer and authz references when those boundaries are affected.
2. Follow the authoritative [Pydantic model rules](CONVENTIONS.md#pydantic-models): typed Pydantic v2 models, frozen-by-default updates, `Money` for every monetary value, and pure-domain imports only.
3. Keep authorization, lifecycle guards, audit writing, persistence, Azure calls, and other side effects in services or infrastructure rather than domain models.
4. Update `tests/models/`, run `uv run pytest tests/models`, then run `bash scripts/validate.sh`. Surface canonical-doc conflicts instead of inventing a local rule.

## UI and component source rules

For every new or changed UI component, page, layout, or interaction. Reusable components go in `WisPay/components/` — documented, page-agnostic, composed by pages; placement and documentation rules: [CONVENTIONS.md → Components](CONVENTIONS.md#components):

1. **Start at Buridan UI**: fetch `https://buridan-ui.reflex.run/llms.txt` and pick the closest component before writing any UI code; read that component's docs page for its API. The llms.txt links point at a dead host — resolve doc pages on `buridan-ui.reflex.run` by appending `.md` (e.g. `https://buridan-ui.reflex.run/docs/components/field.md`). Link the chosen component page in the work notes or PR description. Adopt a component via the Buridan CLI when it becomes part of the app.
2. **`DESIGN.md` + `assets/token.css` govern everything Buridan supplies**: layout, spacing, typography, copy, accessibility, responsive behavior, and visuals. Buridan themes through semantic CSS-variable tokens (`--primary`, `--radius`, … rendered as `bg-background`-style utilities) — map those token names onto the values in `assets/token.css` (exposed through [`WisPay/styles.py`](WisPay/styles.py)) so components pick up WisPay's design system instead of Buridan's defaults.
3. Reuse the closest source example or UI-kit pattern from `E:\projects\WisPay-deisgn` where one exists; do not invent a parallel component API or visual pattern.
4. **Fallback**: when Buridan UI is unavailable, use the [shadcn/ui docs](https://ui.shadcn.com/docs) as the structural reference — Buridan's components deliberately mirror shadcn anatomy — and port the pattern to Reflex Python (`rx` components, state vars, event handlers) under the same `components/` placement and `styles.py` token rules. If Buridan or shadcn guidance conflicts with `DESIGN.md`, or the local design-system source is unavailable, stop and surface the conflict or outage; do not silently substitute generic components.
5. Preserve WisPay domain language and invariants: UI must distinguish recording an external payment from initiating money movement, and it must not hide permission or separation-of-duties explanations.
6. Treat `DESIGN.md` and `assets/token.css` as synchronized snapshots. Update both when the source package changes, and record the source path and retrieval date in the change description.
7. Put reusable Reflex visual values and motion names in [`WisPay/styles.py`](WisPay/styles.py); pages and components should refer to that module instead of duplicating style dictionaries or animation strings.

Buridan supplies component structure and behavior only — domain language, architecture, and security invariants come from the WisPay-doc sources, never from a component library.

## Validation

Run the gate before pushing:

```bash
bash scripts/validate.sh          # lint + format check + types + tests
bash scripts/validate.sh --fix    # auto-fix lint/format, then re-run
```

The pre-push hook runs this automatically; CI re-runs it on every PR.

---

<!-- reflex managed begin (do not edit inside this block; add custom content outside the markers) -->
# Agents

This project uses the **Reflex agent skills** � up-to-date knowledge for building full-stack Python web apps with [Reflex](https://reflex.dev). Install them first, then use them as described below.

## Installing the Skills

Before working on this project, make sure the Reflex skills are available to you.

### Claude Code

If the skills are not already available, install them yourself by running these shell commands:

```bash
claude plugin marketplace add reflex-dev/agent-skills
claude plugin install reflex@reflex-agent-skills
```

Newly installed plugins load on the next session. After installing, tell the user to restart the session so the skills auto-load; until then, read the skill files directly from `~/.claude/plugins/` when you need them.

### Other agents (Cursor, OpenCode, Codex, Pi)

```
npx skills add reflex-dev/agent-skills
```

Or clone https://github.com/reflex-dev/agent-skills and copy the `skills/` folders into your agent's skill directory (see the repo README for paths).

### Verifying

Before writing or editing any Reflex code, confirm these three skills are available: `reflex-docs`, `setup-python-env`, and `reflex-process-management`. If they are not, STOP and run the install step above � do not proceed without them.

## Using the Skills

### Reflex documentation

For anything about Reflex APIs � components, state management, events, styling, database, routing, authentication � use the **reflex-docs** skill rather than relying on memory. It carries current, version-accurate docs.

### Initializing a new Reflex project

When starting a new Reflex project or setting up a development environment, you **must** follow the **setup-python-env** skill before doing anything else.

Do not skip any steps. Do not assume a virtual environment or Reflex is already available � always verify first by following the skill's instructions in order.

After the environment is ready and Reflex is installed, run:

```bash
reflex init
```

Then proceed with the user's request.

### Managing a Reflex process

When you need to compile, run, reload, or debug a Reflex application, follow the **reflex-process-management** skill for the correct sequence and error investigation steps.
<!-- reflex managed end -->

---

## Agent skills

### Issue tracker

Issues are tracked as GitHub issues in `Leonard-Data/WisPay` via the `gh` CLI; feature specs remain under `.scratch/<feature-slug>/spec.md`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical triage labels used as-is: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. The canonical `CONTEXT.md` and `docs/adr/` live in the sibling WisPay-doc repo (`../WisPay-doc`), not in this repo. See `docs/agents/domain.md`.

---

## UI validation with Playwright

When adding or changing a screen under `WisPay/pages/` or a reusable component under `WisPay/components/`:

1. Start Reflex with explicit local ports: `uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1`.
2. Run the browser smoke suite: `uv run pytest -m e2e`.
3. Use the project `playwright-cli` skill with the configured Playwright MCP in `.mcp.json` (or the available browser MCP) to inspect each impacted route at desktop `1440x900` and mobile `390x844`. Capture an accessibility snapshot, screenshot, console errors, network failures, and the primary user flow. Use `playwright-cli show --annotate` when the user needs to mark up the live UI.
4. Compare the result with `E:/projects/WisPay-doc/docs/product/DESIGN.md`. If that canonical repo is unavailable, state the gap and use the design tokens documented in the source file; do not invent a conflicting system.
5. Fix findings and repeat the browser review for at most three iterations. If the UI still misses the design system, stop and ask the user which trade-off or visual direction to choose rather than looping indefinitely.
6. User validation is required before declaring the UI complete: present the rendered route and screenshots, ask the user to approve or request changes, and record any requested follow-up.

Do not treat a passing automated test as design approval. The automated suite checks behavior and basic responsive rendering; the MCP review and explicit user validation are separate gates.

### Required UI-test behavior

When changing `WisPay/pages/`, `WisPay/components/`, `WisPay/layout/`, or their styles:

- Do not only write a test script. Actually start or reuse the Reflex server, open a browser, and run the review before reporting completion.
- Use the DevTools MCP for the live review. The browser must visibly open the app; capture the accessibility snapshot, screenshot, console output, and network failures for every impacted route.
- Always check desktop `1440x900` and mobile `390x844`, plus an unknown route when error-page or routing behavior is affected.
- Compare the rendered result against `docs/product/DESIGN.md` and fix visual or responsive findings before delivery.
- Leave the browser open after the review so the user can inspect the rendered route. Show the screenshot paths and ask the user to approve the UI or request changes.
- Passing `pytest`, compilation, or linting alone is not evidence that the UI review was completed.
