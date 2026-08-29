"""Payment recording queue (``/payments``).

Payment Operators see the queue of Approved requests awaiting external
payment completion. This page is composition only — the real
PaymentRecordingService lands in t3. t4 builds the visual contract per
``DESIGN.md``: explicit "record external reference" copy, three operator
actions (Start / Record / Close), and a no-money-moved tone.

The t4 sample rows are deterministic fixtures matching the lifecycle
coverage matrix in `.scratch/wispay-deploy-build/implementation-tracker.md`.
"""

from __future__ import annotations

import reflex as rx

from WisPay.components import (
    BannerTone,
    PillTone,
    card,
    card_with_heading,
    status_pill,
)
from WisPay.layout.shell import shell
from WisPay.pages.payments_fixtures import PAYMENT_BUCKET, PaymentRow

_KPI_LABELS: tuple[tuple[str, str, str], ...] = (
    ("Ready to start", "Approved requests waiting for operator", "approved"),
    ("In process", "Awaiting external reference capture", "in_process"),
    ("Paid", "Recorded today (sample)", "paid"),
    ("Closure due", "Paid requests awaiting close", "closure_due"),
)


def _kpi(label: str, value: str, *, tone: str = "neutral") -> rx.Component:
    """Render a single KPI tile."""

    return rx.el.div(
        rx.el.span(label, class_name="wispay-kpi-label"),
        rx.el.span(value, class_name="wispay-kpi-value"),
        class_name=f"wispay-kpi tone-{tone}",
    )


def _kpis(rows: list[PaymentRow]) -> rx.Component:
    """Render the four payment KPI tiles."""

    approved = sum(1 for row in rows if row.stage == "approved")
    in_process = sum(1 for row in rows if row.stage == "in_process")
    paid = sum(1 for row in rows if row.stage == "paid")
    closure_due = sum(1 for row in rows if row.stage == "closure_due")
    return rx.el.div(
        _kpi("Ready to start", str(approved)),
        _kpi("In process", str(in_process)),
        _kpi("Paid", str(paid)),
        _kpi("Closure due", str(closure_due)),
        class_name="wispay-payments-kpis",
    )


def _header() -> rx.Component:
    """Render the page header."""

    return rx.el.div(
        rx.el.span("Operations", class_name="wispay-eyebrow"),
        rx.el.h1("Payment recording", class_name="wispay-page-title"),
        rx.el.p(
            "Record external payment completion. WisPay never initiates money movement; "
            "it captures the external reference and routes to closure.",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-payments-header",
    )


def _actions_panel() -> rx.Component:
    """Render the side panel explaining the operator actions."""

    return card(
        rx.el.div(
            rx.el.p("Operator actions", class_name="wispay-card-kicker"),
            rx.el.ul(
                rx.el.li(
                    rx.el.strong("Start", class_name="wispay-payments-action-name"),
                    " — Move an Approved request into Payment in Process.",
                ),
                rx.el.li(
                    rx.el.strong("Record", class_name="wispay-payments-action-name"),
                    " — Capture external reference and proof. Amount must match Approved.",
                ),
                rx.el.li(
                    rx.el.strong("Close", class_name="wispay-payments-action-name"),
                    " — Mark a Paid request Closed. Triggers the read-only banner.",
                ),
                class_name="wispay-payments-action-list",
            ),
            class_name="wispay-card-heading",
        ),
    )


def _queue_card() -> rx.Component:
    """Render the queue card with all payment rows."""

    return card_with_heading(
        kicker="Awaiting operator",
        title="Approved and in-process requests",
        body=_queue_table(),
    )


def _queue_table() -> rx.Component:
    """Render the payment queue table."""

    return rx.el.div(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.el.th("ID", scope="col", class_name="wispay-queue-th"),
                    rx.el.th("Payee", scope="col", class_name="wispay-queue-th"),
                    rx.el.th(
                        "Approved",
                        scope="col",
                        class_name="wispay-queue-th",
                        data_align="right",
                    ),
                    rx.el.th("Stage", scope="col", class_name="wispay-queue-th"),
                    rx.el.th("", scope="col", class_name="wispay-queue-th"),
                )
            ),
            rx.el.tbody(
                *[
                    rx.el.tr(
                        rx.el.td(
                            rx.el.span(row.number, class_name="wispay-mono"),
                            data_th="ID",
                            class_name="wispay-queue-cell-id",
                        ),
                        rx.el.td(
                            rx.el.span(row.payee, class_name="wispay-queue-payee"),
                            rx.el.span(row.subtype, class_name="wispay-queue-sub"),
                            data_th="Payee",
                            class_name="wispay-queue-cell-payee",
                        ),
                        rx.el.td(
                            row.amount_display,
                            data_th="Approved",
                            class_name="wispay-queue-cell is-right is-numeric",
                        ),
                        rx.el.td(
                            status_pill(
                                row.stage_label,
                                tone=(
                                    PillTone.OK
                                    if row.stage in {"in_process", "paid"}
                                    else (
                                        PillTone.ACCENT
                                        if row.stage == "approved"
                                        else PillTone.WARN
                                    )
                                ),
                            ),
                            data_th="Stage",
                        ),
                        rx.el.td(
                            rx.el.div(
                                rx.el.button(
                                    "Start",
                                    type="button",
                                    disabled=row.stage != "approved",
                                    class_name="wispay-button wispay-button-ghost",
                                    title="Starts the Approved → Payment in Process transition",
                                ),
                                rx.el.button(
                                    "Record",
                                    type="button",
                                    disabled=row.stage != "in_process",
                                    class_name="wispay-button wispay-button-secondary",
                                    title="Captures the external reference and proof",
                                ),
                                rx.el.button(
                                    "Close",
                                    type="button",
                                    disabled=row.stage != "paid",
                                    class_name="wispay-button wispay-button-primary",
                                    title="Marks the request Closed (t5 wires the handler)",
                                ),
                                class_name="wispay-action-row",
                            ),
                            data_th="",
                        ),
                        class_name="wispay-queue-row",
                        key=f"payments-row-{row.number}",
                    )
                    for row in PAYMENT_BUCKET
                ]
            ),
            class_name="wispay-queue-table",
        ),
        class_name="wispay-queue-card",
    )


def payments_page() -> rx.Component:
    """Render the payment recording queue."""

    info = rx.el.div(
        rx.el.p("Records, not movement", class_name=f"wispay-banner-lead tone-{BannerTone.INFO}"),
        rx.el.span(
            "WisPay records external payment completion. Money is moved by your banking or ERP "
            "system outside WisPay. Always capture the external reference and proof.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.INFO}",
    )

    return shell(
        rx.el.section(
            _header(),
            info,
            _kpis(PAYMENT_BUCKET),
            rx.el.div(
                _queue_card(),
                _actions_panel(),
                class_name="wispay-payments-grid",
            ),
            aria_label="Payment recording",
            class_name="wispay-page wispay-payments-shell",
        )
    )


__all__ = ["payments_page"]
