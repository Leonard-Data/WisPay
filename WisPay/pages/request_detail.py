"""Payment Request detail screen (``/requests/[number]``).

Composition only: all projections come from ``states.request_tracking_state``
(populated by ``load_detail`` on page load); a tiny local UI state owns the
active tab. Copy is pinned in ``.scratch/request-tracking/spec.md``.
"""

from __future__ import annotations

import reflex as rx

from states.request_tracking import request_tracking_state
from WisPay.layout.shell import shell

_TABS: tuple[str, ...] = ("Summary", "Documents", "Route & Approvals", "Audit")

# Deterministic decorative bar heights for the amount waveform.
_WAVE_HEIGHTS: tuple[int, ...] = tuple(18 + 2 * i + (i % 3) * 4 for i in range(32))


class request_detail_ui_state(rx.State):
    """Active tab for the detail sections (page-local UI concern only)."""

    selected_tab: str = "Summary"

    @rx.event
    def select_tab(self, name: str) -> None:
        """Switch the visible detail section."""

        self.selected_tab = name


def _kv_row(entry: dict[str, str]) -> rx.Component:
    """One label/value row used across summary cards."""

    return rx.el.div(
        rx.el.span(entry["label"], class_name="wispay-detail-kv-label"),
        rx.el.span(entry["value"], class_name="wispay-detail-kv-value"),
        class_name="wispay-detail-kv-row",
    )


def _breadcrumb() -> rx.Component:
    """Back link plus type context."""

    return rx.el.nav(
        rx.link("\u2190 Back to requests", href="/requests", class_name="wispay-detail-backlink"),
        rx.el.span("/", class_name="wispay-detail-crumb-divider"),
        rx.el.span(request_tracking_state.detail["breadcrumb_meta"], class_name="wispay-meta"),
        aria_label="Breadcrumb",
        class_name="wispay-detail-breadcrumb",
    )


def _wave_bars() -> rx.Component:
    """Decorative deterministic waveform (aria-labelled, not data)."""

    return rx.el.div(
        *[
            rx.el.span(
                style={"height": f"{height}px"},
                class_name="wispay-detail-wave-bar",
            )
            for height in _WAVE_HEIGHTS
        ],
        role="img",
        aria_label=request_tracking_state.detail_amount["wave_label"],
        class_name="wispay-detail-wave",
    )


def _amount_panel() -> rx.Component:
    """Warm gross-amount panel with the verbatim records-not-moves note."""

    return rx.el.aside(
        rx.el.span("Gross request", class_name="wispay-detail-amount-label"),
        rx.el.span(
            request_tracking_state.detail_amount["currency"],
            class_name="wispay-detail-amount-currency",
        ),
        rx.el.span(
            request_tracking_state.detail_amount["value"],
            class_name="wispay-detail-amount-value",
        ),
        _wave_bars(),
        rx.el.p(
            request_tracking_state.detail_amount["note"],
            class_name="wispay-detail-amount-note",
        ),
        class_name="wispay-detail-amount",
    )


def _meta_cell(label: str, value: str) -> rx.Component:
    """Meta-grid cell: dt label over dd value (plain strings or vars)."""

    return rx.fragment(
        rx.el.dt(label, class_name="wispay-meta"),
        rx.el.dd(value, class_name="wispay-detail-dd"),
    )


def _header() -> rx.Component:
    """Kicker, number + status row, title, purpose, and meta grid."""

    return rx.el.section(
        rx.el.p(
            f"Request {request_tracking_state.detail['number']}",
            class_name="wispay-detail-kicker",
        ),
        rx.el.div(
            rx.el.span(request_tracking_state.detail["number"], class_name="wispay-meta"),
            rx.el.span(
                rx.el.span(class_name="wispay-pill-dot"),
                request_tracking_state.detail["state"],
                class_name=f"wispay-pill tone-{request_tracking_state.detail['tone']}",
            ),
            rx.cond(
                request_tracking_state.detail["overdue"] != "",
                rx.el.span("Overdue", class_name="wispay-flagchip warn"),
                rx.fragment(),
            ),
            class_name="wispay-detail-title-row",
        ),
        rx.el.h1(request_tracking_state.detail["payee"], class_name="wispay-page-title"),
        rx.el.p(
            request_tracking_state.detail["purpose"],
            class_name="wispay-detail-purpose",
        ),
        rx.el.dl(
            _meta_cell("Payee", request_tracking_state.detail["payee"]),
            _meta_cell("Requester", request_tracking_state.detail["requester"]),
            _meta_cell("Currency", request_tracking_state.detail["currency"]),
            _meta_cell("Created", request_tracking_state.detail["created_display"]),
            class_name="wispay-detail-meta",
        ),
        class_name="wispay-detail-head-main",
    )


def _stepper() -> rx.Component:
    """Seven-milestone lifecycle stepper with branch glyph support."""

    return rx.el.section(
        rx.el.div(
            rx.el.p("Request lifecycle", class_name="wispay-detail-kicker"),
            rx.el.h2("Progress to closure", class_name="wispay-detail-h2"),
            rx.el.span(
                f"Current state \u00b7 {request_tracking_state.detail['state']}",
                class_name="wispay-meta",
            ),
            class_name="wispay-detail-lifecycle-head",
        ),
        rx.el.ol(
            rx.foreach(
                request_tracking_state.stepper,
                lambda step, index: rx.el.li(
                    rx.el.span(
                        rx.cond(step["phase"] == "branch", "\u00d7", index + 1),
                        class_name="wispay-detail-step-dot",
                    ),
                    rx.el.span(step["label"], class_name="wispay-detail-step-label"),
                    class_name=f"wispay-detail-step is-{step['phase']}",
                    key=f"step-{index}",
                ),
            ),
            class_name="wispay-detail-stepper",
        ),
        aria_label="Request lifecycle",
        class_name="wispay-detail-lifecycle",
    )


def _tab_bar() -> rx.Component:
    """Tab strip bound to the local UI state."""

    return rx.el.div(
        rx.el.div(
            role="tablist",
            children=[
                rx.el.button(
                    name,
                    type="button",
                    role="tab",
                    aria_selected=rx.cond(
                        request_detail_ui_state.selected_tab == name,
                        "true",
                        "false",
                    ),
                    on_click=request_detail_ui_state.select_tab(name),  # type: ignore[operator]
                    class_name=rx.cond(
                        request_detail_ui_state.selected_tab == name,
                        "wispay-detail-tab is-active",
                        "wispay-detail-tab",
                    ),
                    key=f"tab-{name}",
                )
                for name in _TABS
            ],
        ),
        id="d-tabs",
        class_name="wispay-detail-tabs",
    )


def _summary_card(title: str, entries: object) -> rx.Component:
    """One kv-card section (entries: state var list of label/value dicts)."""

    return rx.el.section(
        rx.el.h3(title, class_name="wispay-detail-card-title"),
        rx.foreach(entries, _kv_row),
        class_name="wispay-card wispay-detail-summary-card",
    )


def _summary_panel() -> rx.Component:
    """Parties, accounting dimensions, and amount breakdown cards."""

    return rx.el.div(
        _summary_card("Parties", request_tracking_state.parties_rows),
        _summary_card("Accounting dimensions", request_tracking_state.accounting_rows),
        _summary_card("Amount breakdown", request_tracking_state.amount_rows),
        class_name="wispay-detail-summary-grid",
    )


def _documents_panel() -> rx.Component:
    """Honest documents placeholder until persistence lands."""

    return rx.el.div(
        rx.el.section(
            rx.el.h3("Document checklist", class_name="wispay-detail-card-title"),
            rx.foreach(
                request_tracking_state.doc_rows,
                lambda entry: rx.el.p(entry["note"], class_name="wispay-body-muted"),
            ),
            class_name="wispay-card wispay-detail-summary-card",
        ),
        class_name="wispay-detail-panel",
    )


def _route_panel() -> rx.Component:
    """Read-only approval-route section with its honest empty state."""

    return rx.el.div(
        rx.el.section(
            rx.el.h3("Approval route", class_name="wispay-detail-card-title"),
            rx.cond(
                request_tracking_state.route_steps.length() > 0,  # type: ignore[attr-defined]
                rx.foreach(request_tracking_state.route_steps, _kv_row),
                rx.el.p(
                    "No route yet \u2014 routing is generated after evidence validation.",
                    class_name="wispay-body-muted",
                ),
            ),
            class_name="wispay-card wispay-detail-summary-card",
        ),
        class_name="wispay-detail-panel",
    )


def _audit_panel() -> rx.Component:
    """Append-only audit feed plus chain verification chip."""

    return rx.el.div(
        rx.el.section(
            rx.el.div(
                rx.el.h3("Audit trail", class_name="wispay-detail-card-title"),
                rx.el.span(
                    f"{request_tracking_state.audit_count} events",
                    class_name="wispay-meta",
                ),
                rx.cond(
                    request_tracking_state.chain_verified,
                    rx.el.span("Chain verified", class_name="wispay-pill tone-ok"),
                    rx.fragment(),
                ),
                class_name="wispay-detail-audit-head",
            ),
            rx.cond(
                request_tracking_state.audit_rows.length() > 0,  # type: ignore[attr-defined]
                rx.el.ol(
                    rx.foreach(
                        request_tracking_state.audit_rows,
                        lambda event: rx.el.li(
                            rx.el.span(event["when"], class_name="wispay-meta"),
                            rx.el.span(
                                rx.el.strong(event["action"]),
                                class_name="wispay-detail-audit-action",
                            ),
                            rx.el.span(event["actor"], class_name="wispay-body-muted"),
                            rx.cond(
                                event["reason"] != "",
                                rx.el.span(
                                    "\u2014 ",
                                    event["reason"],
                                    class_name="wispay-detail-audit-reason",
                                ),
                                rx.fragment(),
                            ),
                            class_name="wispay-detail-audit-row",
                            key=f"audit-{event['when']}-{event['action']}",
                        ),
                    ),
                    class_name="wispay-detail-audit-list",
                ),
                rx.el.p("No audit events.", class_name="wispay-body-muted"),
            ),
            class_name="wispay-card wispay-detail-summary-card",
        ),
        class_name="wispay-detail-panel",
    )


def _panels() -> rx.Component:
    """Active tab panel switch."""

    return rx.el.div(
        rx.cond(
            request_detail_ui_state.selected_tab == "Summary",
            _summary_panel(),
            rx.cond(
                request_detail_ui_state.selected_tab == "Documents",
                _documents_panel(),
                rx.cond(
                    request_detail_ui_state.selected_tab == "Route & Approvals",
                    _route_panel(),
                    _audit_panel(),
                ),
            ),
        ),
        id="d-panels",
        class_name="wispay-detail-tabpanels",
    )


def _not_found() -> rx.Component:
    """Inline unknown-number presentation."""

    return rx.el.div(
        rx.el.h1("Request not found", class_name="wispay-empty-title"),
        rx.el.p(
            "Check the number, or open the queue to find your request.",
            class_name="wispay-empty-copy",
        ),
        rx.link(
            "Back to requests",
            href="/requests",
            class_name="wispay-button wispay-button-secondary",
        ),
        class_name="wispay-request-empty",
    )


def request_detail_page() -> rx.Component:
    """Render one Payment Request's tracking detail."""

    return shell(
        rx.cond(
            request_tracking_state.not_found,
            _not_found(),
            rx.el.section(
                _breadcrumb(),
                rx.el.div(_header(), _amount_panel(), class_name="wispay-detail-header"),
                _stepper(),
                _tab_bar(),
                _panels(),
                aria_label="Payment Request detail",
                class_name="wispay-page wispay-detail-page",
            ),
        )
    )
