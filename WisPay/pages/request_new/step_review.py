"""Review step (step 4) of the create-payment-request wizard.

Renders blocking issues, advisory warnings, and the request summary before
submission. Submission itself routes through ``RequestCreateState.submit``.

Usage::

    from WisPay.pages.request_new.step_review import step_review

    rx.cond(RequestCreateState.step == 4, step_review(), ...)
"""

from __future__ import annotations

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.pages.request_new.controls import subtype_heading


def summary_row(label: str, value: str | rx.Var[str] | rx.Component) -> rx.Component:
    """Render one description-list row of the review summary.

    Args:
        label: Row caption.
        value: Plain copy, state var, or component rendered into the cell.

    Usage::
        summary_row("Title", RequestCreateState.title)
    """

    return rx.el.div(
        rx.el.dt(label),
        rx.el.dd(value, class_name="wispay-new-num"),
        class_name="wispay-new-summary-row",
    )


def _or_dash(value: rx.Var[str]) -> rx.Component:
    """Render a summary value with an em-dash fallback while empty."""

    return rx.cond(value != "", value, "—")


def validation_banner() -> rx.Component:
    """Render the blocking-issue banner with jump-back shortcuts.

    Usage::
        validation_banner()
    """

    return rx.cond(
        RequestCreateState.issue_count > 0,
        rx.el.div(
            rx.el.div(
                rx.el.span("!", class_name="wispay-new-validation-mark"),
                rx.el.span("Items must be fixed before submission"),
                class_name="wispay-new-validation-title",
            ),
            rx.el.ul(
                rx.foreach(
                    RequestCreateState.blocking,
                    lambda item: rx.el.li(item, key=item),
                ),
                rx.foreach(
                    RequestCreateState.field_issue_rows,
                    lambda row: rx.el.li(row["message"], key=row["field"]),
                ),
                class_name="wispay-new-error-list",
            ),
            rx.el.div(
                rx.el.button(
                    "Edit details",
                    type="button",
                    class_name="wispay-button wispay-new-button-secondary",
                    on_click=RequestCreateState.go_to_step(2),  # type: ignore[operator]
                ),
                rx.el.button(
                    "Add documents",
                    type="button",
                    class_name="wispay-button wispay-new-button-ghost",
                    on_click=RequestCreateState.go_to_step(3),  # type: ignore[operator]
                ),
                class_name="wispay-new-inline-actions",
            ),
            role="alert",
            class_name="wispay-new-validation is-error",
        ),
        rx.fragment(),
    )


def warnings_banner() -> rx.Component:
    """Render the advisory warning banner for non-blocking review notes.

    Usage::
        warnings_banner()
    """

    return rx.cond(
        RequestCreateState.warnings.length() > 0,  # type: ignore[attr-defined]
        rx.el.div(
            rx.el.div(
                rx.el.span("i", class_name="wispay-new-validation-mark"),
                rx.el.span("Review before submitting"),
                class_name="wispay-new-validation-title",
            ),
            rx.el.ul(
                rx.foreach(
                    RequestCreateState.warnings,
                    lambda item: rx.el.li(item, key=item),
                ),
                class_name="wispay-new-error-list",
            ),
            role="status",
            class_name="wispay-new-validation is-warn",
        ),
        rx.fragment(),
    )


def review_summary() -> rx.Component:
    """Render the description list summarizing the drafted request.

    Usage::
        review_summary()
    """

    return rx.el.dl(
        summary_row("Title", RequestCreateState.title),
        summary_row("Type", subtype_heading()),
        summary_row("Payee", _or_dash(RequestCreateState.payee_display)),
        summary_row(
            "Gross amount",
            rx.cond(
                RequestCreateState.gross_preview != "",
                RequestCreateState.gross_preview,
                "Enter amounts to preview",
            ),
        ),
        summary_row("Cost center", RequestCreateState.cost_center),
        summary_row("Currency", RequestCreateState.currency),
        summary_row("Accounting period", _or_dash(RequestCreateState.accounting_period)),
        summary_row("Budget period", RequestCreateState.budget_period),
        class_name="wispay-new-card wispay-new-review-summary",
    )


def lifecycle_note() -> rx.Component:
    """Render the post-submission lifecycle note under the summary.

    Usage::
        lifecycle_note()
    """

    return rx.el.p(
        "Submitting freezes this request data for review; corrections after "
        "submission go through Return-for-correction. ",
        rx.el.strong("WisPay approves and records payments; it never initiates money movement."),
        class_name="wispay-new-review-note",
    )


def step_review() -> rx.Component:
    """Render the full Review step panel ahead of submission.

    Usage::
        rx.cond(RequestCreateState.step == 4, step_review(), ...)
    """

    return rx.el.section(
        rx.el.p("Step 4 · Review", class_name="wispay-new-eyebrow"),
        rx.el.h2("Review before submitting", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p("Confirm the request and its evidence.", class_name="wispay-new-muted"),
        validation_banner(),
        warnings_banner(),
        review_summary(),
        lifecycle_note(),
        class_name="wispay-new-panel",
    )
