"""Payment Request queue screen.

Composition only per CONVENTIONS: every projection comes from
``states.request_tracking_state`` (services do the work); this module wires
controls to handlers and renders the pinned copy from
``.scratch/request-tracking/spec.md``.
"""

from __future__ import annotations

import reflex as rx

from states.request_tracking import request_tracking_state
from WisPay.layout.shell import shell
from WisPay.models import LifecycleState

_STATUS_OPTIONS: tuple[str, ...] = tuple(state.value for state in LifecycleState)

_EMPTY_NO_REQUESTS_TITLE = "No requests yet"
_EMPTY_NO_REQUESTS_COPY = "Start by creating a new payment request."
_EMPTY_NO_MATCHES_TITLE = "No requests match your filters"
_EMPTY_NO_MATCHES_COPY = "Adjust or clear filters to see more results."


def _filter_field(label: str, control: rx.Component) -> rx.Component:
    """Render a labelled queue filter control."""

    return rx.el.label(
        rx.el.span(label, class_name="wispay-filter-label"),
        control,
        class_name="wispay-filter-field",
    )


def _search_input() -> rx.Component:
    """Free-text search over number, payee, invoice, and purpose."""

    return rx.el.input(
        id="q-search",
        type="search",
        placeholder="ID, payee, invoice, purpose\u2026",
        value=request_tracking_state.search_text,
        on_change=request_tracking_state.set_search,
        class_name="wispay-filter-control",
    )


def _status_select() -> rx.Component:
    """Canonical lifecycle state filter."""

    return rx.el.select(
        rx.el.option("All statuses", value="", disabled=True),
        *[rx.el.option(name, value=name) for name in _STATUS_OPTIONS],
        id="q-status",
        value=request_tracking_state.status_filter,
        on_change=request_tracking_state.set_status,
        class_name="wispay-filter-control",
    )


def _family_select() -> rx.Component:
    """Vendor / Employee family filter."""

    return rx.el.select(
        rx.el.option("All families", value=""),
        rx.el.option("Vendor", value="Vendor"),
        rx.el.option("Employee", value="Employee"),
        id="q-family",
        value=request_tracking_state.family_filter,
        on_change=request_tracking_state.set_family,
        class_name="wispay-filter-control",
    )


def _cost_center_select() -> rx.Component:
    """Cost-center filter fed by the session's stored dimensions."""

    return rx.el.select(
        rx.el.option("All cost centers", value=""),
        rx.foreach(
            request_tracking_state.cost_center_options,
            lambda code: rx.el.option(code, value=code),
        ),
        id="q-costcenter",
        value=request_tracking_state.cost_center_filter,
        on_change=request_tracking_state.set_cost_center,
        class_name="wispay-filter-control",
    )


def _request_filters() -> rx.Component:
    """Queue filter card."""

    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2("Filters", class_name="wispay-page-title wispay-filter-heading-title"),
                rx.el.span(
                    "Applied live to your submitted requests",
                    class_name="wispay-filter-note",
                ),
                class_name="wispay-filter-heading",
            ),
            rx.el.div(
                _filter_field("Search", _search_input()),
                _filter_field("Status", _status_select()),
                _filter_field("Family", _family_select()),
                _filter_field("Cost center", _cost_center_select()),
                class_name="wispay-filter-grid",
            ),
            class_name="wispay-requests-filters wispay-card",
        ),
        aria_label="Payment Request queue filters",
        class_name="wispay-requests-filter-section",
    )


def _result_meta() -> rx.Component:
    """Live-region result count and reset affordance."""

    return rx.el.div(
        rx.el.span(
            rx.cond(
                request_tracking_state.result_count == 1,
                "1 request",
                f"{request_tracking_state.result_count} requests",
            ),
            class_name="wispay-queue-count",
            aria_live="polite",
        ),
        rx.cond(
            (request_tracking_state.search_text != "")
            | (request_tracking_state.status_filter != "")
            | (request_tracking_state.family_filter != "")
            | (request_tracking_state.cost_center_filter != ""),
            rx.el.button(
                "Reset filters",
                type="button",
                id="q-reset",
                on_click=request_tracking_state.reset_filters,
                class_name="wispay-button wispay-button-ghost wispay-queue-reset",
            ),
        ),
        class_name="wispay-queue-meta",
    )


def _empty_no_requests() -> rx.Component:
    """Honest empty state before anything has been submitted."""

    return rx.el.div(
        rx.icon("inbox", size=28),
        rx.el.p(_EMPTY_NO_REQUESTS_TITLE, class_name="wispay-empty-title"),
        rx.el.p(_EMPTY_NO_REQUESTS_COPY, class_name="wispay-empty-copy"),
        rx.link(
            "New Payment Request",
            href="/requests/new",
            class_name="wispay-button wispay-button-primary",
        ),
        class_name="wispay-request-empty",
    )


def _empty_no_matches() -> rx.Component:
    """Honest empty state when filters exclude every tracked request."""

    return rx.el.div(
        rx.el.p(_EMPTY_NO_MATCHES_TITLE, class_name="wispay-empty-title"),
        rx.el.p(_EMPTY_NO_MATCHES_COPY, class_name="wispay-empty-copy"),
        rx.el.button(
            "Clear all filters",
            type="button",
            on_click=request_tracking_state.reset_filters,
            class_name="wispay-button wispay-button-ghost",
        ),
        class_name="wispay-request-empty",
    )


def _load_error() -> rx.Component:
    """Readable failure banner; never a blank page."""

    return rx.el.div(
        rx.el.strong("Could not load your requests."),
        rx.el.span(request_tracking_state.load_error),
        id="q-error",
        role="alert",
        class_name="wispay-queue-error",
    )


def _header_cell(label: str) -> rx.Component:
    """One sortable-looking header cell (sorting deferred; spec decision 9)."""

    return rx.el.th(label, scope="col", class_name="wispay-queue-th")


def _pill(tone: str, label: str) -> rx.Component:
    """Status pill with its tone dot."""

    return rx.el.span(
        rx.el.span(class_name="wispay-pill-dot"),
        label,
        class_name=f"wispay-pill tone-{tone}",
    )


def _row(row: dict[str, str]) -> rx.Component:
    """One queue row; every td carries data-th for the mobile card fallback."""

    return rx.el.tr(
        rx.el.td(
            rx.el.span(
                row["type_icon"],
                class_name="wispay-queue-typeicon",
                aria_hidden="true",
            ),
            rx.el.button(
                row["number"],
                type="button",
                on_click=request_tracking_state.open_detail(row["number"]),  # type: ignore[operator]
                class_name="wispay-queue-id",
            ),
            data_th="ID",
            class_name="wispay-queue-cell-id",
        ),
        rx.el.td(
            rx.el.span(row["payee"], class_name="wispay-queue-payee"),
            rx.el.span(row["family_subtype"], class_name="wispay-queue-sub"),
            data_th="Payee",
            class_name="wispay-queue-cell-payee",
        ),
        rx.el.td(
            row["amount_display"],
            data_th="Gross",
            class_name="wispay-queue-amt",
        ),
        rx.el.td(
            _pill(row["tone"], row["state"]),
            data_th="Status",
        ),
        rx.el.td(
            rx.cond(
                row["overdue"] != "",
                rx.el.span("Overdue", class_name="wispay-flagchip warn"),
                "\u2014",
            ),
            data_th="Flags",
        ),
        rx.el.td(
            f"{row['submitted_display']} ({row['age_days']}d)",
            data_th="Submitted",
        ),
        rx.el.td(row["due_display"], data_th="Due"),
        class_name="wispay-queue-row",
    )


def _queue_table() -> rx.Component:
    """Responsive queue table mirroring the design-system table anatomy."""

    return rx.el.div(
        rx.el.table(
            rx.el.caption("Payment Requests you submitted", class_name="wispay-sr-only"),
            rx.el.thead(
                rx.el.tr(
                    _header_cell("ID"),
                    _header_cell("Payee"),
                    _header_cell("Gross"),
                    _header_cell("Status"),
                    _header_cell("Flags"),
                    _header_cell("Submitted"),
                    _header_cell("Due"),
                )
            ),
            rx.el.tbody(
                rx.foreach(request_tracking_state.rows, _row),
                id="q-rows",
            ),
            class_name="wispay-queue-table",
        ),
        class_name="wispay-card wispay-queue-card",
    )


def requests_page() -> rx.Component:
    """Render the Payment Request queue: filters, count, and tracked rows."""

    return shell(
        rx.el.section(
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Payment Request queue",
                        class_name="wispay-eyebrow",
                    ),
                    rx.el.h1("Requests", class_name="wispay-page-title"),
                    rx.el.p(
                        "Track every payment request you have submitted, "
                        "from intake to payment record.",
                        class_name="wispay-page-lede",
                    ),
                    class_name="wispay-request-heading",
                ),
                rx.link(
                    rx.icon("plus", size=16),
                    rx.el.span("New Payment Request"),
                    href="/requests/new",
                    class_name="wispay-button wispay-button-primary",
                ),
                class_name="wispay-request-toolbar",
            ),
            _request_filters(),
            rx.cond(
                request_tracking_state.load_error != "",
                _load_error(),
                rx.fragment(),
            ),
            _result_meta(),
            rx.cond(
                request_tracking_state.empty_kind == "no-requests",
                _empty_no_requests(),
                rx.cond(
                    request_tracking_state.empty_kind == "no-matches",
                    _empty_no_matches(),
                    _queue_table(),
                ),
            ),
            aria_label="Payment Requests",
            class_name="wispay-page wispay-requests-page",
        )
    )
