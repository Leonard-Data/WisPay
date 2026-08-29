"""Finance Review queue (``/finance-review``).

Finance reviewers triage Submitted requests across four review buckets
(Budget, Compliance, Evidence, Approval). This page is composition only —
the actual service calls live in ``states.finance_review_state`` (added in
t5); t4 builds the visual contract per ``DESIGN.md`` and the lifecycle
coverage matrix in `.scratch/wispay-deploy-build/implementation-tracker.md`.
"""

from __future__ import annotations

from collections import OrderedDict

import reflex as rx

from WisPay.components import (
    BannerTone,
    PillTone,
    card,
    card_with_heading,
    status_pill,
)
from WisPay.layout.shell import shell
from WisPay.pages.finance_review_buckets import (
    APPROVAL_BUCKET,
    BUDGET_BUCKET,
    COMPLIANCE_BUCKET,
    EVIDENCE_BUCKET,
    FinanceReviewRow,
)

_QUEUE_LABELS: dict[str, str] = OrderedDict(
    (
        ("budget", "Budget Review"),
        ("compliance", "Compliance Review"),
        ("evidence", "Evidence Validation"),
        ("approval", "Approval Pending"),
    )
)


def _kpi(label: str, value: str, meta: str = "") -> rx.Component:
    """Render one KPI tile for the queue header."""

    children: list[rx.Component] = [
        rx.el.span(label, class_name="wispay-kpi-label"),
        rx.el.span(value, class_name="wispay-kpi-value"),
    ]
    if meta:
        children.append(rx.el.span(meta, class_name="wispay-kpi-meta"))
    return rx.el.div(*children, class_name="wispay-kpi")


def _kpis(rows_by_bucket: dict[str, list[FinanceReviewRow]]) -> rx.Component:
    """Render the four KPI tiles summarizing the four review buckets."""

    counts = {key: len(rows_by_bucket.get(key, [])) for key in _QUEUE_LABELS}
    total = sum(counts.values())
    return rx.el.div(
        _kpi("Open in review", str(total)),
        _kpi(
            "Budget exceptions",
            str(sum(1 for row in rows_by_bucket.get("budget", []) if row.is_exception)),
            meta="Awaiting budget owner",
        ),
        _kpi(
            "Compliance returned",
            str(sum(1 for row in rows_by_bucket.get("compliance", []) if row.is_returned)),
        ),
        _kpi(
            "Approval pending",
            str(counts.get("approval", 0)),
            meta="Sample actors only",
        ),
        class_name="wispay-finrev-kpis",
    )


def _header() -> rx.Component:
    """Render the eyebrow / heading / lede block."""

    return rx.el.div(
        rx.el.span("Finance Review", class_name="wispay-eyebrow"),
        rx.el.h1("Review queues", class_name="wispay-page-title"),
        rx.el.p(
            "Triage Submitted Payment Requests across Budget, Compliance, "
            "Evidence, and Approval. Each bucket is permission-scoped.",
            class_name="wispay-page-lede",
        ),
        class_name="wispay-finrev-header",
    )


def _bucket_card(
    *,
    key: str,
    rows: list[FinanceReviewRow],
) -> rx.Component:
    """Render one bucket card (queue header + table of rows)."""

    body = _bucket_table(rows)
    return card_with_heading(
        kicker=_QUEUE_LABELS[key],
        title="Awaiting your action",
        body=body,
    )


def _bucket_table(rows: list[FinanceReviewRow]) -> rx.Component:
    """Render the queue rows for a bucket."""

    if not rows:
        return rx.el.p(
            "No requests waiting in this bucket.",
            class_name="wispay-body-muted",
        )
    return rx.el.div(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.el.th("ID", scope="col", class_name="wispay-queue-th"),
                    rx.el.th("Payee", scope="col", class_name="wispay-queue-th"),
                    rx.el.th(
                        "Gross",
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
                            data_th="Gross",
                            class_name="wispay-queue-cell is-right is-numeric",
                        ),
                        rx.el.td(
                            status_pill(
                                row.stage_label,
                                tone=(
                                    PillTone.WARN
                                    if row.is_exception
                                    else (PillTone.OK if row.is_passed else PillTone.INFO)
                                ),
                            ),
                            data_th="Stage",
                        ),
                        rx.el.td(
                            rx.el.button(
                                "Review",
                                type="button",
                                class_name="wispay-button wispay-button-secondary wispay-queue-row-action",
                                title="Open request detail (t5)",
                                disabled=True,
                            ),
                            data_th="",
                        ),
                        class_name="wispay-queue-row",
                        key=f"finrev-row-{row.number}",
                    )
                    for row in rows
                ]
            ),
            class_name="wispay-queue-table",
        ),
        class_name="wispay-queue-card",
    )


def finance_review_page() -> rx.Component:
    """Render the Finance Review queue screen."""

    rows_by_bucket: dict[str, list[FinanceReviewRow]] = {
        "budget": BUDGET_BUCKET,
        "compliance": COMPLIANCE_BUCKET,
        "evidence": EVIDENCE_BUCKET,
        "approval": APPROVAL_BUCKET,
    }
    info = rx.el.div(
        rx.el.p("Sample configuration", class_name="wispay-banner-lead tone-info"),
        rx.el.span(
            "Rules, thresholds, and the duplicate detection heuristic are prototype defaults "
            "(rule set v1). Finance signs the production configuration per Phase 0.",
            class_name="wispay-banner-copy",
        ),
        role="status",
        class_name=f"wispay-banner tone-{BannerTone.INFO}",
    )

    return shell(
        rx.el.section(
            _header(),
            info,
            _kpis(rows_by_bucket),
            rx.el.div(
                card(
                    _bucket_card(key="budget", rows=rows_by_bucket["budget"]),
                ),
                card(
                    _bucket_card(
                        key="compliance",
                        rows=rows_by_bucket["compliance"],
                    ),
                ),
                card(
                    _bucket_card(key="evidence", rows=rows_by_bucket["evidence"]),
                ),
                card(
                    _bucket_card(key="approval", rows=rows_by_bucket["approval"]),
                ),
                class_name="wispay-finrev-grid",
            ),
            aria_label="Finance Review",
            class_name="wispay-page wispay-finrev-shell",
        )
    )


__all__ = ["finance_review_page"]
