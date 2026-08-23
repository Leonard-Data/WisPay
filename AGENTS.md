# WisPay — application repo

WisPay is the internal portal for **Vendor and Employee Payment Requests**: submission through approval and Finance's recording of external payment completion.
This repo holds the working **Reflex** application. It is **not** the source of truth for domain or design.

## Source of truth

The canonical domain glossary, delivery plan, design system, and ADRs live in the **WisPay-doc** repo (`E:/projects/WisPay-doc`). Read these **before** writing feature code:

- `CONTEXT.md` — canonical domain glossary and invariants (actors, request categories, lifecycle, security invariants). Do not invent conflicting terminology.
- `wispay-delivery-plan.md` — phased delivery plan and release gates.
- `docs/product/DESIGN.md` — design system for this Reflex app.
- `docs/product/APP-SETUP.md` — scaffold guide, DB schema, Azure Document Intelligence integration.
- `docs/adr/` — architecture decision records. Surface conflicts; don't silently override.

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

- [`CONVENTIONS.md`](CONVENTIONS.md) — coding rules (style, Reflex patterns, Pydantic, security/audit invariants, testing).
- [`scripts/validate.sh`](scripts/validate.sh) — the pre-validation gate (lint + format + types + tests). **Must pass before any commit/push.**
- [`.pre-commit-config.yaml`](.pre-commit-config.yaml) — git hooks (ruff on commit, full gate on push).
- `.scratch/` — local Markdown issue tracker (one feature per dir: `spec.md` + `issues/NN-slug.md`). Mirrors WisPay-doc's convention.

## Security & audit invariants (from CONTEXT.md)

Non-negotiable for any payment-related change:

1. The requester cannot approve their own request.
2. Only an approved request can enter payment processing.
3. Only authorized Finance users can record payment completion.
4. Every submission, review, approval, rejection, change, delegation, and payment update is audit logged.
5. Submitted financial records and audit events are never hard-deleted.
6. Secrets (Azure keys, SQL passwords) live in `.env` only — never in code or commits.

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
