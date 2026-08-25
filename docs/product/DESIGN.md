# WisPay Design System

> Checked-in application snapshot of `C:\Users\binh.phung\projects\WisPay-Design-System\DESIGN.md`.
>
> This file is the visual implementation contract for the WisPay Reflex app. Keep the source package and this snapshot synchronized when the system changes. Domain terminology, workflow invariants, and architecture remain governed by the WisPay-doc repository.
>
> **Component source:** before implementing or changing a component, fetch and inspect [Buridan UI's current component index](https://buridan-ui.reflex.run/llms.txt). Use its Reflex component guidance together with the tokens and patterns in this file; do not invent a replacement component API.
>
> **Reflex token bridge:** [`assets/design-tokens.css`](assets/design-tokens.css) exposes the source tokens with a `--ws-` prefix for `WisPay/styles.py` and other component code.
>
**Product context**

WisPay is an internal request-to-pay portal for vendor invoices, employee reimbursements, advances, settlements, and approved internal expenditure. It organizes the lifecycle from request intake through approval, external payment recording, reconciliation, and audit. WisPay never initiates money movement; it records decisions and external references.

This system is a source-grounded extraction from the Web Prototype project and the ElevenLabs design-system binding. It is intentionally operational: clear status, responsible actor, amount, due date, and next action must remain legible at a glance.

## Product context

WisPay's primary surfaces are the role-aware dashboard, request search workspace, submission wizard, approval queue, finance review queue, payment-record queue, request detail, audit search, reports, and sample configuration studio. The core capability is a traceable, permission-aware lifecycle with local persistence, immutable audit events, separation-of-duties guards, and external payment recording.

## Visual summary

A white, achromatic workspace uses whisper-light display type, compact black/gray utility text, warm-stone emphasis surfaces, and crimson only for primary action and active attention. A 264px sidebar anchors the application; the content frame stays readable at 1200px. Subtle rings and half-pixel insets define surfaces instead of heavy borders. A segmented waveform amount strip is the single expressive flourish and appears only on request-detail amount panels.

## Color

The source-backed palette is `#ffffff` canvas, `#f5f5f5` inset, `#f5f2ef` warm context, `#000000` primary ink, `#4e4e4e` secondary ink, `#777169` metadata, `#e5e5e5` border, and `#cf000f` action crimson. Semantic green, yellow, and danger tones remain small status signals.

## Typography

Waldenburg at weight 300 is display type, Inter carries body and UI copy, and Geist Mono carries request IDs, timestamps, labels, and tabular amounts. The source fallbacks remain part of the portable contract because no font files were supplied.

## 1. Foundations

### Color

The color system is intentionally achromatic: white canvas, pale gray inset surfaces, warm stone context, black primary ink, warm gray metadata, and crimson action. Semantic green, yellow, and danger tones are small state signals only. The values below are source-backed and preserved in `assets/tokens.css`.

### Typography

The type system pairs light Waldenburg display text with Inter UI copy and Geist Mono data labels. Display hierarchy is light rather than bold; IDs, amounts, timestamps, and rule traces use mono for alignment and scanability.

### Core tokens

The source token file in `assets/tokens.css` is preserved verbatim. The six portable foundation tokens are:

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#ffffff` | Primary canvas and elevated surface |
| `--surface` | `#f5f5f5` | Inset panels, hover, neutral status |
| `--fg` | `#000000` | Headings, primary text, completed state |
| `--muted` | `#777169` | Metadata, labels, helper copy |
| `--border` | `#e5e5e5` | Table rules and structural dividers |
| `--accent` | `#cf000f` | Primary action and active navigation |

Supporting source values include `--surface-warm: #f5f2ef`, `--fg-2: #4e4e4e`, `--accent-hover: #ad000d`, `--accent-active: #8f000b`, `--success: #16a34a`, `--warn: #eab308`, `--danger: #dc2626`, and the blue `--focus-ring`.

Color is deliberately quiet. Semantic colors appear in small pills, dots, meters, and banners; they never become large decorative fields.

### Typography

| Role | Family | Weight / treatment | Typical size |
| --- | --- | --- | --- |
| Display | `Waldenburg`, fallback system sans | 300, tight leading, slight negative tracking | 32–48px |
| Body / UI | `Inter`, fallback system sans | 400–600, +0.16–0.18px tracking | 13–16px |
| Mono / data | `Geist Mono`, fallback monospace | Tabular numerals, uppercase metadata | 10–13px |

Display type creates a calm, premium surface. Inter carries operational reading. Geist Mono is reserved for request IDs, amounts, timestamps, labels, and rule traces. No font files were supplied by the source project; fallbacks are therefore part of the contract.

### Spacing

The source uses a 4px base rhythm: `4, 8, 12, 16, 20, 24, 32, 48px`. Primary sections breathe at `96px` desktop, `64px` tablet, and `48px` phone. Use the smallest scale that keeps separate decisions readable; do not introduce arbitrary values when a source token fits.

### Shape and elevation

- Radius is consistently compact: `5px` for cards, controls, tabs, banners, and the nominal pill token.
- Use `--elev-ring` for most cards: a faint ring plus a short lift.
- Use `--elev-raised` for secondary buttons and raised controls.
- Warm surfaces use the source's brown-tinted shadow to keep the stone panel grounded without visual heaviness.
- Avoid glossy gradients, large radii, and ornamental shadows.

## 2. Layout & composition

### Application shell

- Fixed left sidebar: `264px` wide on desktop.
- Sidebar sections: Workspace, Review, Operations, Governance.
- Guided flow panel: Requests → New Request → Approvals → Finance Review → Payments.
- Persona switcher stays in the sidebar footer; the mobile bar exposes menu, language, notifications, and brand.
- Main content uses `--container-max: 1200px` with `24px` desktop gutters, `16px` tablet gutters, and `12px` phone gutters.
- At `1024px`, the sidebar becomes a drawer. At `768px`, multi-column grids collapse and tables become stacked cards. At `430px`, page padding tightens without horizontal scrolling.

### Page hierarchy

1. Eyebrow / section context in mono uppercase.
2. Light display heading that states the job of the screen.
3. One short explanatory sentence when needed.
4. KPI, queue, table, or detail content grouped into shallow surfaces.
5. One primary action per task cluster; secondary and ghost actions support it.

### Density

WisPay is data-dense but not compressed. Tables use 10–14px metadata, 13–15px rows, and generous horizontal alignment. IDs and currency values align with mono numerals. Cards separate major decisions; do not turn every row into a card.

## 3. Components

### Brand mark and wordmark

The WisPay mark is four narrow bars with varied heights followed by a light wordmark. The extracted SVG in `assets/brand-mark.svg` is a faithful package asset; it is not used as a decorative illustration. Keep the mark black on the white canvas and do not recolor it for status.

### Navigation

Sidebar links are 42px minimum height, flush-left, and grouped by uppercase mono labels. Default links use `--fg-2`; hover uses `--surface` plus `--fg`; active uses a faint crimson-tinted surface, crimson text, and a crimson dot. Locked links remain visibly disabled with an explanatory title and never become clickable.

### Buttons

- `.btn-primary`: crimson fill, white text; reserved for the next consequential step.
- `.btn-secondary`: white fill with raised shadow; common for exports and alternate navigation.
- `.btn-ghost`: transparent, muted text by default; hover restores `--fg` on `--surface`.
- `.btn-danger-ghost`: transparent danger text for cancellation/rejection, never a large red field.
- Minimum height is 44px. Small buttons stay at least 34px for dense toolbars.
- Hover changes the background or shadow, never the text to a lower-contrast color.

### Cards and panels

`.card` is the default white surface. `.card-inset` uses `--surface` for filters and nested content. `.card-warm` is reserved for contextual emphasis, gross amount panels, and explanatory callouts. Keep padding at 20–24px for primary panels and 12–16px for compact rows.

### Status pills and flags

Status pills use a dot plus a short label. Neutral, progress, information, success, warning, danger, and accent tones are soft fills with readable dark text. Derived badges such as Overdue, Duplicate, Exception, Window, and Settlement use mono or compact text and stay adjacent to the status rather than replacing it.

### Banners

Banners are full-width message rows with 14–20px padding, a short strong lead, and a restrained semantic tint. Use danger for blocking over-budget exceptions, warning for duplicate or deadline attention, info for explanatory framing, and success for recorded-payment confirmation.

### Tables

Use uppercase mono headers, 1px rules, right-aligned numeric columns, and row hover on `--surface`. The first column is usually an ID or type glyph. At phone widths, hide the table header and expose each cell's label through `data-th`; never clip critical values.

### Forms

Labels are 12–13px muted Inter. Inputs are 44px minimum with `--surface` fill and an inset ring. Use explicit helper and error copy. Selects keep the source chevron treatment. Required data, warnings, and blocking conditions are visible adjacent to the field or submit action.

### Lifecycle stepper

The stepper makes the route legible: small numbered nodes, black for completed steps, blue focus ring for the active step, thin connecting rules, and mono timestamps under completed nodes. Returned, rejected, and cancelled branches use a small danger treatment and never distort the main sequence.

### Tabs

Tabs are a single horizontal row with a bottom rule. The active tab uses `--fg` and a 2px bottom line; hover uses `--surface`. Counts are compact mono badges. On small screens, keep the row horizontally scrollable rather than squeezing labels into unreadable widths.

### Waveform amount strip

The request-detail header may include one segmented strip that encodes the amount context. Bars are filled, varied in height, and dim after the active portion. It is finance-native audio heritage, not a decorative chart. Always pair it with a plain gross amount and a text description for accessibility.

### Route, audit, and payment surfaces

Route steps use a 30px sequence column, assignee and decision detail, and a status pill. Audit entries show timestamp, actor, action, field changes, and reason. Payment records always use language such as “record,” “external reference,” and “processed outside WisPay.” Never write “transfer,” “debit,” or “sent” as if WisPay moved money.

### Dialogs, toasts, empty and loading states

Dialogs use a centered white modal, subtle overlay blur, one primary confirmation, and one ghost cancel. Toasts are dark with white text; error toasts use the danger color. Empty states explain what is missing and provide a single next step. Skeletons use the source shimmer only for loading, not as decoration.

## 4. Motion & interaction

- Fast transitions: `150ms`; base transitions: `200ms`; easing: `cubic-bezier(0.2, 0, 0, 1)`.
- Hover uses a surface tint, shadow change, or `translateY(-1px)` for cards.
- Active buttons move down by `1px`.
- Page entry uses a small opacity / 8px translate only where the source shell already does so.
- Every focusable element receives the source blue `--focus-ring` through `:focus-visible`.
- Disabled controls may reduce contrast, but their explanation must remain available through visible copy or title.
- `prefers-reduced-motion: reduce` removes nonessential animation.
- Persist persona, language, and demo state through the source localStorage model when building an applied prototype.

## 5. Voice & content

Use precise, human operational language. Prefer “Awaiting my action,” “Returned for correction,” “Record payment,” “External reference,” “Pending closure,” and “Sample configuration — not policy.” Sentence case is the default. Metadata and rules use uppercase mono labels. Keep copy short enough to survive dense tables and translated EN / VI variants.

Never imply that WisPay moves funds, determines tax or legal outcomes, or replaces policy. Metrics derived from seed data must be labeled as prototype or session calculations, not production claims.

## 6. Responsive contract

- No horizontal page scroll at 360, 390, 430, 600, 768, 820, 1024, 1366, 1440, or 1920px.
- All touch targets are at least 44px.
- Tables collapse to readable stacked rows below 768px.
- Detail header stacks below 900px; metadata becomes two columns below 640px and one-column key/value rows below 430px.
- Sidebars become drawers at 1024px; the mobile bar remains visible while open.

## 7. Anti-patterns

- No purple gradients, glassmorphism layers, generic SaaS blue, or cream canvas.
- No Inter / Roboto / Arial / Fraunces as display type.
- No emoji as functional icons.
- No large color fields for status; use dots, pills, lines, and small banners.
- No repeated solid primary buttons for one action in the same viewport.
- No clipped table cells, orphaned labels, accidental overlaps, or placeholder boxes where source evidence already provides a real component.
- No fabricated performance, spend, policy, or compliance values.
- No hidden action because of role ambiguity: show a disabled control with a reason when the source interaction calls for it.
- No payment copy that implies WisPay initiates money movement.

## 8. Package map

- `colors_and_type.css` — portable foundation and preview helpers.
- `assets/tokens.css` — preserved source token and application layer.
- `assets/brand-mark.svg` — extracted source mark.
- `build/` — runtime icon assets used by the source shell.
- `preview/` — focused review cards and applied reference surfaces.
- `source-examples/` — substantial source HTML / JS / CSS examples preserved intact.
- `ui_kits/app/` — applied, interactive interface kit for shell, dashboard, queue, and request detail patterns.
