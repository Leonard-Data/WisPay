# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

Single-context (no monorepo). The canonical domain docs do **not** live in this repo — they live in the sibling **WisPay-doc** repo, as documented in this repo's `AGENTS.md` ("Source of truth" section).

## Before exploring, read these (in WisPay-doc, not here)

The canonical docs live at sibling path `../WisPay-doc` (`C:\Users\binh.phung\projects\WisPay-doc` in this environment):

- **`CONTEXT.md`** — canonical domain glossary and invariants (actors, request categories, lifecycle, security invariants). Do not invent conflicting terminology.
- **`wispay-delivery-plan.md`** — phased delivery plan and release gates.
- **`docs/product/DESIGN.md`** — product-level design intent and context.
- **`docs/product/APP-SETUP.md`** — scaffold guide, DB schema, Azure Document Intelligence integration.
- **`docs/adr/`** — architecture decision records. Surface conflicts; don't silently override.

The app-level visual implementation contract is [`DESIGN.md`](../../DESIGN.md), synchronized from `C:\Users\binh.phung\projects\WisPay-Design-System\DESIGN.md`. Its source-derived tokens live in [`assets/design-tokens.css`](../../assets/design-tokens.css). Use the app contract for visual implementation while keeping domain, security, and architecture decisions in WisPay-doc.

## Do not create a local CONTEXT.md or docs/adr/ in this repo

This repo (`WisPay`) holds the working Reflex application and is **not** the source of truth for domain or design (per `AGENTS.md`). Domain terms and ADRs are authored in WisPay-doc. If `/domain-modeling` resolves a new term or decision, record it in WisPay-doc, not here.

## If WisPay-doc is not accessible

If the configured WisPay-doc path is not mounted/available, fall back to the domain summary embedded in this repo's `AGENTS.md` (the "Security & audit invariants" and "Source of truth" sections) and surface the gap explicitly: note which canonical docs you could not read and what you assumed instead. Do not treat the local design snapshot as a substitute for missing domain or architecture decisions.

## Use the glossary's vocabulary

When your output names a domain concept (issue title, refactor proposal, hypothesis, test name), use the term as defined in WisPay-doc's `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (record it in WisPay-doc via `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR in WisPay-doc's `docs/adr/`, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (...), but worth reopening because…_
