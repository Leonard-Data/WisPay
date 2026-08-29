"""Success-measure panel and spend analysis (``/reports``).

Composition-only page that visualises the A11 acceptance criterion
(permission-scoped CSV exports) plus the spend by cost center and the
spend by family breakdowns. Real data lands in t5 via
``WisPay.services.report``.
"""

from __future__ import annotations

import reflex as rx

from WisPay.components import BannerTone, card_with_heading
from WisPay.layout.shell import shell
from WisPay.pages.reports_fixtures import (
    EXPORT_CENTERS,
    SPEND_BY_COST_CENTER,
    SPEND_BY_FAMILY,
    SPEND_BY_PERIOD,
    SpendBar,
)


def _header() -> rx.Component:
    """Render the page header."""

    return rx.el.div(
        rx.el.span("Insights", class_name="wispay-eyebrow"),
        rx.el.h1("Reports & exports", class_name="wispay-page-title"),
        rx.el.p(
            "Read-only analytics on sample request data. All export scopes "
            "respect the active persona's permissions.",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-reports-header",
    )


def _kpi(label: str, value: str) -> rx.Component:
    """Render one summary KPI tile."""

    return rx.el.div(
        rx.el.span(label, class_name="wispay-kpi-label"),
        rx.el.span(value, class_name="wispay-kpi-value"),
        class_name="wispay-kpi",
    )


def _kpis() -> rx.Component:
    """Render the headline KPI row."""

    return rx.el.div(
        _kpi("Requests in window", "148"),
        _kpi("Approved", "82"),
        _kpi("Median cycle time", "3.4d"),
        _kpi("Over-budget exceptions", "4"),
        class_name="wispay-payments-kpis",
    )


def _bar_row(bar: SpendBar) -> rx.Component:
    """Render one spend bar row."""

    return rx.el.div(
        rx.el.span(bar.label, class_name="wispay-reports-bar-label"),
        rx.el.span(
            rx.el.span(
                class_name="wispay-reports-bar-fill",
                style={"width": f"{bar.percent}%"},
            ),
            class_name="wispay-reports-bar-track",
        ),
        rx.el.span(bar.value, class_name="wispay-reports-bar-value"),
        rx.el.span(f"{bar.percent}%", class_name="wispay-reports-bar-share"),
        class_name="wispay-reports-bar-row",
        key=f"spend-{bar.label}",
    )


def _spend_by_cost_center() -> rx.Component:
    """Render the spend-by-cost-center card."""

    return card_with_heading(
        kicker="Spend by cost center",
        title="Trailing 90 days",
        body=rx.el.div(
            *[_bar_row(bar) for bar in SPEND_BY_COST_CENTER],
            class_name="wispay-reports-section",
        ),
    )


def _spend_by_family() -> rx.Component:
    """Render the spend-by-family card."""

    return card_with_heading(
        kicker="Spend by family",
        title="Vendor vs Employee",
        body=rx.el.div(
            *[_bar_row(bar) for bar in SPEND_BY_FAMILY],
            class_name="wispay-reports-section",
        ),
    )


def _spend_by_period() -> rx.Component:
    """Render the period summary card (no bars, just labelled rows)."""

    return card_with_heading(
        kicker="Spend by period",
        title="Trailing 6 months",
        body=rx.el.div(
            *[
                rx.el.div(
                    rx.el.span(period, class_name="wispay-reports-period"),
                    rx.el.span(value, class_name="wispay-reports-bar-value"),
                    rx.el.span(change, class_name="wispay-reports-bar-share"),
                    class_name="wispay-reports-bar-row",
                    key=f"period-{period}",
                )
                for period, value, change in SPEND_BY_PERIOD
            ]
        ),
    )


def _export_center() -> rx.Component:
    """Render the export center card (A11 contract)."""

    return card_with_heading(
        kicker="Export center",
        title="Permission-scoped CSV",
        body=rx.el.div(
            *[
                rx.el.div(
                    rx.el.span(name, class_name="wispay-reports-export-name"),
                    rx.el.span(scope, class_name="wispay-reports-export-meta"),
                    rx.el.button(
                        "Download",
                        type="button",
                        disabled=True,
                        class_name="wispay-button wispay-button-secondary",
                        title="t5 wires the export handler with UTF-8 BOM",
                    ),
                    class_name="wispay-reports-export-row",
                    key=f"export-{name}",
                )
                for name, scope in EXPORT_CENTERS
            ],
            class_name="wispay-reports-export",
        ),
    )


def reports_page() -> rx.Component:
    """Render the reports page."""

    notice = rx.el.div(
        rx.el.p(
            "Sample metrics",
            class_name=f"wispay-banner-lead tone-{BannerTone.INFO}",
        ),
        rx.el.span(
            "Values shown here are derived from the sample fixture set, not live data. "
            "Production numbers appear after Phase 0 sign-off.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.INFO}",
    )

    return shell(
        rx.el.section(
            _header(),
            notice,
            _kpis(),
            rx.el.div(
                _spend_by_cost_center(),
                _spend_by_family(),
                class_name="wispay-reports-grid",
            ),
            rx.el.div(
                _spend_by_period(),
                _export_center(),
                class_name="wispay-reports-grid",
            ),
            aria_label="Reports and exports",
            class_name="wispay-page wispay-reports-shell",
        )
    )


__all__ = ["reports_page"]
