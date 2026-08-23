# Issue tracker

Local Markdown issue tracker for the WisPay app. Mirrors the convention in **WisPay-doc**.

## Layout

- One feature per directory: `.scratch/<feature-slug>/`
- Feature specification: `.scratch/<feature-slug>/spec.md`
- Implementation tickets: `.scratch/<feature-slug>/issues/<NN>-<slug>.md` (number from `01`)
- A `Status:` line near the top tracks triage state
- Discussion under a `## Comments` heading

## Triage labels (canonical)

`needs-triage` · `needs-info` · `ready-for-agent` · `ready-for-human` · `wontfix`

See `WisPay-doc/docs/agents/triage-labels.md` for the authoritative definitions.
