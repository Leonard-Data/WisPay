"""Dashboard landing page (role-aware workspace overview).

t4 builds the visual contract per ``DESIGN.md``: persona-aware widgets
sourced from ``WisPay.services.user_context`` once t3/t5 wire persistence.
Until then, the page renders the design-system chrome and labels every
metric as a sample fixture so the design audit can confirm the layout
without leaking fabricated numbers as production claims (per the
"no fabricated performance, spend, policy, or compliance values" rule).
"""

from __future__ import annotations

import reflex as rx

from WisPay.components import (
    BannerTone,
    card,
    card_warm,
    card_with_heading,
)
from WisPay.layout.shell import shell
from WisPay.pages.dashboard_fixtures import (
    DASHBOARD_ACTIVITY,
    DASHBOARD_KPIS,
    DashboardKpi,
)


def _kpi_tile(kpi: DashboardKpi) -> rx.Component:
    """Render one KPI tile."""

    return rx.el.div(
        rx.el.span(kpi.label, class_name="wispay-kpi-label"),
        rx.el.span(kpi.value, class_name="wispay-kpi-value"),
        rx.el.span(kpi.meta, class_name="wispay-kpi-meta"),
        class_name="wispay-kpi",
        key=f"dashboard-kpi-{kpi.label}",
    )


def _header() -> rx.Component:
    """Render the dashboard header."""

    return rx.el.div(
        rx.el.span("Workspace", class_name="wispay-eyebrow"),
        rx.el.h1("A clear place to start", class_name="wispay-page-title"),
        rx.el.p(
            "Your queues, awaiting actions, and recent activity — at a glance. "
            "Switch personas in the sidebar to see a different scope.",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-dashboard-header",
    )


def _kpi_row() -> rx.Component:
    """Render the dashboard KPI row."""

    return rx.el.div(
        *[_kpi_tile(kpi) for kpi in DASHBOARD_KPIS],
        class_name="wispay-dashboard-kpis",
    )


def _activity_row(entry: dict[str, str]) -> rx.Component:
    """Render one activity feed row."""

    return rx.el.div(
        rx.el.span(entry["when"], class_name="wispay-audit-time"),
        rx.el.span(entry["action"], class_name="wispay-audit-action"),
        rx.el.span(entry["subject"], class_name="wispay-audit-actor"),
        rx.el.span(entry["actor"], class_name="wispay-audit-actor"),
        class_name="wispay-audit-row",
        key=f"dashboard-activity-{entry['when']}-{entry['subject']}",
    )


def _activity_card() -> rx.Component:
    """Render the recent-activity card."""

    return card_with_heading(
        kicker="Recent activity",
        title="Across your queues",
        body=rx.el.div(
            *[_activity_row(entry) for entry in DASHBOARD_ACTIVITY],
        ),
    )


def _shortcut_card() -> rx.Component:
    """Render the primary shortcut card."""

    return card_warm(
        rx.el.div(
            rx.el.span("Workspace", class_name="wispay-card-kicker"),
            rx.el.h3("Start a new Payment Request", class_name="wispay-page-title"),
            rx.el.p(
                "Build a complete request across the four-step wizard. The wizard "
                "blocks submission until every required document is attached.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card-heading",
        ),
        rx.el.div(
            rx.el.button(
                "New Payment Request",
                type="button",
                class_name="wispay-button wispay-button-primary",
                title="Opens the create-request wizard (t5 wires the navigation)",
                disabled=True,
            ),
            rx.el.link(
                "View requests",
                href="/requests",
                class_name="wispay-button wispay-button-secondary",
            ),
            class_name="wispay-action-row",
        ),
    )


def _lifecycle_explainer() -> rx.Component:
    """Render the lifecycle explainer card (per DESIGN.md)."""

    return card(
        rx.el.div(
            rx.el.p("Request-to-Pay lifecycle", class_name="wispay-card-kicker"),
            rx.el.p(
                "From intake to closure, WisPay keeps the controlled flow visible without "
                "implying that WisPay moves funds. Payment recording captures the external "
                "reference once your banking or ERP system processes the payment.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card-heading",
        ),
    )


def _persona_chip(name: str, role: str, is_active: bool = False) -> rx.Component:
    """Render one persona pill (read-only chip; t5 wires the switcher)."""

    class_name = "wispay-persona-card"
    if is_active:
        class_name += " is-active"
    return rx.el.div(
        rx.el.span(name, class_name="wispay-persona-name"),
        rx.el.span(role, class_name="wispay-persona-meta"),
        class_name=class_name,
        key=f"persona-chip-{name}",
    )


def _persona_card() -> rx.Component:
    """Render the active persona panel (A13 hook)."""

    return card_with_heading(
        kicker="Acting as",
        title="Active persona (sample)",
        body=rx.el.div(
            rx.el.div(
                _persona_chip("Line Manager", "First approver · v1", is_active=True),
                _persona_chip("Finance Reviewer / AP", "Compliance · Evidence · Payments"),
                _persona_chip("CFO / Executive Approver", "Over-budget append"),
                _persona_chip("Auditor", "Read-only audit stream"),
                class_name="wispay-persona-grid",
            ),
        ),
    )


def dashboard_page() -> rx.Component:
    """Render the role-aware dashboard landing page."""

    notice = rx.el.div(
        rx.el.p(
            "Sample configuration",
            class_name=f"wispay-banner-lead tone-{BannerTone.INFO}",
        ),
        rx.el.span(
            "Queues, KPIs, and activity shown here are derived from the prototype fixture set. "
            "Live values appear once the persistence layer (t5) connects the dashboard to "
            "the durable stores.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.INFO}",
    )

    return shell(
        rx.el.section(
            _header(),
            notice,
            _kpi_row(),
            rx.el.div(
                _shortcut_card(),
                _lifecycle_explainer(),
                class_name="wispay-reports-grid",
            ),
            _persona_card(),
            _activity_card(),
            aria_label="Dashboard",
            class_name="wispay-page wispay-dashboard-shell",
        )
    )


__all__ = ["dashboard_page"]
