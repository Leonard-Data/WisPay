"""Sample configuration studio (``/admin``).

Administrator surface for the prototype: approval threshold matrix, route
simulator, document-requirement editor. t4 builds the visual contract per
``DESIGN.md``; the persistence and versioned-rule editing lands in t3/t5.

The admin surfaces are explicitly labeled "Sample configuration — not
policy" per the prototype PRD and the design voice rules.
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
from WisPay.pages.admin_fixtures import (
    DOCUMENT_REQUIREMENTS,
    PERSONA_GRID,
    THRESHOLD_ROWS,
    ThresholdRow,
)


def _header() -> rx.Component:
    """Render the page header."""

    return rx.el.div(
        rx.el.span("Configuration", class_name="wispay-eyebrow"),
        rx.el.h1("Sample configuration studio", class_name="wispay-page-title"),
        rx.el.p(
            "Tune rule set v1 for the prototype. Real production rules ship "
            "after Finance sign-off (Phase 0).",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-admin-header",
    )


def _threshold_row(row: ThresholdRow) -> rx.Component:
    """Render one row in the approval threshold matrix."""

    return rx.el.div(
        rx.el.span(row.role, class_name="wispay-admin-th-label"),
        rx.el.span(row.up_to, class_name="wispay-admin-th-value"),
        rx.el.span(row.fallback, class_name="wispay-admin-th-value"),
        rx.el.span(row.version, class_name="wispay-admin-th-version"),
        class_name="wispay-admin-thresholds",
        key=f"admin-threshold-{row.role}",
    )


def _threshold_section() -> rx.Component:
    """Render the approval threshold matrix card."""

    return card_with_heading(
        kicker="Approval thresholds",
        title="Rule set v1 — current draft",
        body=rx.el.div(
            rx.el.div(
                rx.el.span("Role", class_name="wispay-admin-th-label"),
                rx.el.span("Up to", class_name="wispay-admin-th-value"),
                rx.el.span("Escalation", class_name="wispay-admin-th-value"),
                rx.el.span("Version", class_name="wispay-admin-th-version"),
                class_name="wispay-admin-thresholds",
            ),
            *[_threshold_row(row) for row in THRESHOLD_ROWS],
        ),
    )


def _persona_card(name: str, role: str) -> rx.Component:
    """Render one persona tile (read-only list)."""

    return rx.el.div(
        rx.el.span(name, class_name="wispay-persona-name"),
        rx.el.span(role, class_name="wispay-persona-meta"),
        class_name="wispay-persona-card",
        key=f"persona-{name}",
    )


def _persona_section() -> rx.Component:
    """Render the persona matrix card (A13 hook)."""

    return card_with_heading(
        kicker="Personas",
        title="8 personas, distinct navigation",
        body=rx.el.div(
            *[_persona_card(name, role) for name, role in PERSONA_GRID],
            class_name="wispay-persona-grid",
        ),
    )


def _documents_section() -> rx.Component:
    """Render the document requirement matrix card."""

    return card_with_heading(
        kicker="Document requirements",
        title="Per family and subtype",
        body=rx.el.div(
            *[
                rx.el.div(
                    rx.el.span(
                        entry["family"],
                        class_name="wispay-admin-th-label",
                    ),
                    rx.el.span(
                        entry["required"],
                        class_name="wispay-admin-th-value",
                    ),
                    rx.el.span(
                        entry["optional"],
                        class_name="wispay-admin-th-value",
                    ),
                    rx.el.span(
                        entry["version"],
                        class_name="wispay-admin-th-version",
                    ),
                    class_name="wispay-admin-thresholds",
                    key=f"docs-{entry['family']}",
                )
                for entry in DOCUMENT_REQUIREMENTS
            ]
        ),
    )


def _route_simulator() -> rx.Component:
    """Render the route simulator card."""

    return card(
        rx.el.div(
            rx.el.p("Route simulator", class_name="wispay-card-kicker"),
            rx.el.p(
                "Generate a frozen approval route for a sample Vendor request "
                "against the active rule set. Routes never change after submit.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card-heading",
        ),
        rx.el.div(
            rx.el.label(
                rx.el.span("Request number", class_name="wispay-filter-label"),
                rx.el.input(
                    placeholder="WPR-2026-0041",
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            rx.el.label(
                rx.el.span("Amount", class_name="wispay-filter-label"),
                rx.el.input(
                    placeholder="VND 1,240,000,000",
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            rx.el.label(
                rx.el.span("Cost center", class_name="wispay-filter-label"),
                rx.el.select(
                    rx.el.option("CC-OPS-01", value="CC-OPS-01"),
                    rx.el.option("CC-FIN-04", value="CC-FIN-04"),
                    rx.el.option("CC-IT-22", value="CC-IT-22"),
                    class_name="wispay-filter-control",
                ),
                class_name="wispay-filter-field",
            ),
            class_name="wispay-filter-grid",
        ),
        rx.el.div(
            rx.el.button(
                "Generate route",
                type="button",
                disabled=True,
                class_name="wispay-button wispay-button-primary",
                title="t5 wires the route simulator handler",
            ),
            rx.el.span(
                status_pill("Rule set v1", tone=PillTone.INFO),
                class_name="wispay-admin-rule-set",
            ),
            class_name="wispay-action-row",
        ),
    )


def admin_page() -> rx.Component:
    """Render the sample configuration studio."""

    notice = rx.el.div(
        rx.el.p(
            "Sample configuration — not policy",
            class_name=f"wispay-banner-lead tone-{BannerTone.WARNING}",
        ),
        rx.el.span(
            "Thresholds, document requirements, and rule versions shown here "
            "are prototype defaults. Finance signs the production configuration "
            "in Phase 0 before any change applies to a live request.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.WARNING}",
    )

    return shell(
        rx.el.section(
            _header(),
            notice,
            rx.el.div(
                _threshold_section(),
                _route_simulator(),
                class_name="wispay-admin-grid",
            ),
            rx.el.div(
                _documents_section(),
                _persona_section(),
                class_name="wispay-admin-grid",
            ),
            aria_label="Configuration",
            class_name="wispay-page wispay-admin-shell",
        )
    )


__all__ = ["admin_page"]
