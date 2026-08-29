"""Read-only audit search (``/audit``).

Auditors see the immutable audit stream. This page is composition only —
the real AuditTrailService lands in t5; t4 builds the visual contract per
``DESIGN.md``: read-only surface, immutable copy, no destructive actions,
expandable diff rows for consequential events.

The sample rows below are deterministic fixtures covering the lifecycle
events described in the BS-1 tracker §6 A14 acceptance criterion.
"""

from __future__ import annotations

import reflex as rx

from WisPay.components import BannerTone, card, card_with_heading
from WisPay.layout.shell import shell
from WisPay.pages.audit_fixtures import AUDIT_ROWS, AuditRow


def _header() -> rx.Component:
    """Render the page header."""

    return rx.el.div(
        rx.el.span("Governance", class_name="wispay-eyebrow"),
        rx.el.h1("Audit trail", class_name="wispay-page-title"),
        rx.el.p(
            "Read-only, append-only audit stream. Search by request number, "
            "actor, or action; expand consequential events to see before / after values.",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-audit-header",
    )


def _search_card() -> rx.Component:
    """Render the search form card."""

    return card(
        rx.el.div(
            rx.el.p("Search", class_name="wispay-card-kicker"),
            rx.el.p(
                "Filter the audit stream. Read-only — no delete, no edit.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card-heading",
        ),
        rx.el.div(
            rx.el.label(
                rx.el.span("Request number", class_name="wispay-filter-label"),
                rx.el.input(
                    placeholder="WPR-2026-…",
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            rx.el.label(
                rx.el.span("Actor", class_name="wispay-filter-label"),
                rx.el.input(
                    placeholder="alice@contoso.com",
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            rx.el.label(
                rx.el.span("Action", class_name="wispay-filter-label"),
                rx.el.select(
                    rx.el.option("All actions", value=""),
                    rx.el.option("Submitted", value="Submitted"),
                    rx.el.option("Reviewed", value="Reviewed"),
                    rx.el.option("Approved", value="Approved"),
                    rx.el.option("Rejected", value="Rejected"),
                    rx.el.option("Returned", value="Returned"),
                    rx.el.option("Changed", value="Changed"),
                    rx.el.option("Payment Updated", value="Payment Updated"),
                    rx.el.option("Cancelled", value="Cancelled"),
                    rx.el.option("Exception Recorded", value="Exception Recorded"),
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            rx.el.label(
                rx.el.span("Window", class_name="wispay-filter-label"),
                rx.el.select(
                    rx.el.option("Last 7 days", value="7d"),
                    rx.el.option("Last 30 days", value="30d"),
                    rx.el.option("Last 90 days", value="90d"),
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            class_name="wispay-filter-grid",
        ),
    )


def _audit_row(row: AuditRow) -> rx.Component:
    """Render one audit row."""

    return rx.el.div(
        rx.el.span(row.when, class_name="wispay-audit-time"),
        rx.el.span(row.action, class_name="wispay-audit-action"),
        rx.el.span(row.actor, class_name="wispay-audit-actor"),
        rx.el.span(row.scope, class_name="wispay-audit-actor"),
        class_name="wispay-audit-row",
        key=f"audit-{row.when}-{row.action}-{row.scope}",
    )


def _stream_card() -> rx.Component:
    """Render the append-only audit stream card."""

    return card_with_heading(
        kicker=f"{len(AUDIT_ROWS)} events · chain verified",
        title="Audit stream (sample)",
        body=rx.el.div(
            *[_audit_row(row) for row in AUDIT_ROWS],
        ),
    )


def audit_page() -> rx.Component:
    """Render the audit page."""

    notice = rx.el.div(
        rx.el.p("Append-only", class_name=f"wispay-banner-lead tone-{BannerTone.INFO}"),
        rx.el.span(
            "Audit events are hash-chained and never edited or deleted by normal application "
            "functions. Use the export center to share a permission-scoped snapshot.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.INFO}",
    )

    return shell(
        rx.el.section(
            _header(),
            notice,
            rx.el.div(
                _search_card(),
                _stream_card(),
                class_name="wispay-audit-grid",
            ),
            aria_label="Audit trail",
            class_name="wispay-page wispay-audit-shell",
        )
    )


__all__ = ["audit_page"]
