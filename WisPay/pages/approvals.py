"""Approval tracking screen (/approvals)."""

from __future__ import annotations

import reflex as rx

from states.approvals import QueueRow, TimelineRow, approvals_state
from WisPay.layout.shell import shell


def _status_banner() -> rx.Component:
    """Render the live region for service outcomes and setup hints."""
    return rx.cond(
        approvals_state.status_message != "",
        rx.el.div(
            rx.el.span(approvals_state.status_message, class_name="wispay-appr-status-text"),
            rx.el.button(
                "Dismiss",
                on_click=approvals_state.dismiss_status,
                class_name="wispay-button wispay-appr-status-dismiss",
                type="button",
            ),
            role="status",
            aria_live="polite",
            class_name="wispay-card wispay-appr-status",
        ),
        rx.fragment(),
    )


def _route_tool() -> rx.Component:
    """Render the sample route-generation control for Submitted requests."""
    return rx.box(
        rx.box(
            rx.text("Route a submitted request", class_name="wispay-card-kicker"),
            rx.text(
                "Routes generate once from versioned rule set v1 and are then frozen "
                "with the request. Sample configuration — not policy.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card-heading",
        ),
        rx.el.div(
            rx.el.input(
                placeholder="WPR-2026-0001",
                value=approvals_state.route_number,
                on_change=approvals_state.set_route_number,
                aria_label="Request number to route",
                class_name="wispay-appr-route-input",
            ),
            rx.el.button(
                "Generate approval route",
                on_click=approvals_state.create_route,
                class_name="wispay-button wispay-button-secondary",
                type="button",
            ),
            class_name="wispay-appr-route-row",
        ),
        class_name="wispay-card wispay-appr-route-tool",
    )


def _actor_switcher() -> rx.Component:
    """Render the labeled sample-actor switcher."""
    return rx.el.div(
        rx.el.span("Acting as (sample configuration):", class_name="wispay-appr-actor-label"),
        rx.foreach(
            approvals_state.actor_options,
            lambda name: rx.cond(
                approvals_state.actor_name == name,
                rx.el.button(
                    name,
                    on_click=lambda: approvals_state.switch_actor(name),  # type: ignore[operator]
                    class_name="wispay-appr-actor-chip is-active",
                    type="button",
                    aria_pressed="true",
                ),
                rx.el.button(
                    name,
                    on_click=lambda: approvals_state.switch_actor(name),  # type: ignore[operator]
                    class_name="wispay-appr-actor-chip",
                    type="button",
                    aria_pressed="false",
                ),
            ),
        ),
        role="group",
        aria_label="Sample actor switcher",
        class_name="wispay-appr-actor-bar",
    )


def _queue_row(row: QueueRow, index: int) -> rx.Component:
    """Render one pending decision row."""
    return rx.el.tr(
        rx.el.td(rx.el.span(row.request_number, class_name="wispay-mono")),
        rx.el.td(
            rx.el.div(
                rx.el.span(row.title, class_name="wispay-appr-title"),
                rx.el.span(row.beneficiary, class_name="wispay-appr-sub"),
            )
        ),
        rx.el.td(rx.el.span(row.amount_display, class_name="wispay-mono")),
        rx.el.td(row.requester_name),
        rx.el.td(rx.el.span(row.approver_role, class_name="wispay-appr-pill")),
        rx.el.td(row.due_display),
        rx.el.td(
            rx.el.button(
                "Review & decide",
                on_click=lambda: approvals_state.select_row_at(index),  # type: ignore[operator]
                class_name="wispay-button wispay-appr-row-action",
                type="button",
            )
        ),
    )


def _queue_table() -> rx.Component:
    """Render the pending-decisions table or its honest empty state."""
    return rx.box(
        rx.box(
            rx.text("Waiting on you", class_name="wispay-card-kicker"),
            class_name="wispay-card-heading",
        ),
        rx.cond(
            approvals_state.queue_rows.length() > 0,  # type: ignore[attr-defined]
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th("Number"),
                            rx.el.th("Request"),
                            rx.el.th("Amount"),
                            rx.el.th("Requester"),
                            rx.el.th("Approver role"),
                            rx.el.th("Due"),
                            rx.el.th(""),
                        )
                    ),
                    rx.el.tbody(
                        rx.foreach(approvals_state.queue_rows, _queue_row),
                    ),
                ),
                class_name="wispay-appr-table-wrap",
            ),
            rx.el.div(
                rx.icon("inbox", size=24),
                rx.el.h3("No approvals are waiting on you", class_name="wispay-empty-title"),
                rx.el.p(
                    "When a submitted request is routed and a step is assigned to the "
                    "selected sample actor, it appears here.",
                    class_name="wispay-card-copy",
                ),
                class_name="wispay-request-empty",
            ),
        ),
        class_name="wispay-card wispay-appr-queue",
    )


def _decision_panel() -> rx.Component:
    """Render the decision panel for the selected route step."""
    return rx.cond(
        approvals_state.selected_key != "",
        rx.box(
            rx.box(
                rx.text("Record a decision", class_name="wispay-card-kicker"),
                rx.el.div(
                    rx.el.span(
                        approvals_state.selected_summary["request_number"],
                        class_name="wispay-mono",
                    ),
                    rx.el.span(
                        approvals_state.selected_summary["title"],
                        class_name="wispay-appr-title",
                    ),
                    rx.el.span(
                        approvals_state.selected_summary["beneficiary"],
                        class_name="wispay-appr-sub",
                    ),
                    rx.el.span(
                        approvals_state.selected_summary["amount_display"],
                        class_name="wispay-appr-sub wispay-mono",
                    ),
                    class_name="wispay-appr-selected-meta",
                ),
                class_name="wispay-card-heading",
            ),
            rx.el.label(
                "Reason (required to reject or return)",
                rx.el.textarea(
                    value=approvals_state.reason_text,
                    on_change=approvals_state.set_reason,
                    placeholder="Why is this being returned or rejected?",
                    aria_label="Decision reason",
                    class_name="wispay-appr-reason",
                ),
                class_name="wispay-appr-reason-field",
            ),
            rx.el.div(
                rx.el.button(
                    "Approve",
                    on_click=lambda: approvals_state.decide("Approved"),  # type: ignore[operator]
                    class_name="wispay-button wispay-button-primary",
                    type="button",
                ),
                rx.el.button(
                    "Return for correction",
                    on_click=lambda: approvals_state.decide("Returned"),  # type: ignore[operator]
                    class_name="wispay-button wispay-button-secondary",
                    type="button",
                ),
                rx.el.button(
                    "Reject",
                    on_click=lambda: approvals_state.decide("Rejected"),  # type: ignore[operator]
                    class_name="wispay-button wispay-appr-danger",
                    type="button",
                ),
                class_name="wispay-appr-actions",
            ),
            rx.el.p(
                "Recording a decision is audit evidence. It never moves money; Finance "
                "records external payment completion separately.",
                class_name="wispay-appr-footnote",
            ),
            class_name="wispay-card wispay-appr-decision",
        ),
        rx.fragment(),
    )


def _timeline_card() -> rx.Component:
    """Render the frozen route timeline for the selection."""
    return rx.cond(
        approvals_state.timeline_rows.length() > 0,  # type: ignore[attr-defined]
        rx.box(
            rx.box(
                rx.el.div(
                    rx.text("Approval route", class_name="wispay-card-kicker"),
                    rx.el.span(
                        approvals_state.selected_summary["outcome"],
                        class_name="wispay-appr-pill",
                        data_state=approvals_state.selected_summary["outcome"].lower(),
                    ),
                    class_name="wispay-appr-timeline-head",
                ),
                class_name="wispay-card-heading",
            ),
            rx.el.ol(
                rx.foreach(approvals_state.timeline_rows, _timeline_item),
                class_name="wispay-appr-timeline",
            ),
            class_name="wispay-card wispay-appr-timeline-card",
        ),
        rx.fragment(),
    )


def _timeline_item(item: TimelineRow) -> rx.Component:
    """Render one vertical-timeline step (Buridan Timeline anatomy, ported)."""
    return rx.el.li(
        rx.el.span(
            class_name="wispay-appr-dot",
            data_state=item.decision.lower(),
            aria_hidden=True,
        ),
        rx.el.div(
            rx.el.span(
                f"Step {item.sequence} · {item.approver_role}",
                class_name="wispay-appr-step-date",
            ),
            rx.el.p(item.approver_name, class_name="wispay-appr-step-title"),
            rx.el.div(
                rx.el.span(
                    item.decision,
                    class_name="wispay-appr-pill",
                    data_state=item.decision.lower(),
                ),
                rx.cond(
                    item.is_current,
                    rx.el.span("Awaiting decision", class_name="wispay-appr-current-note"),
                    rx.fragment(),
                ),
                class_name="wispay-appr-step-status",
            ),
            rx.cond(
                item.reason != "",
                rx.el.p(item.reason, class_name="wispay-appr-step-reason"),
                rx.fragment(),
            ),
            class_name="wispay-appr-step-body",
        ),
        class_name="wispay-appr-step",
    )


def approvals_page() -> rx.Component:
    """Render the approval tracking workspace."""
    return shell(
        rx.el.section(
            rx.el.div(
                rx.text("Approval tracking", class_name="wispay-eyebrow"),
                rx.heading("Approvals", class_name="wispay-page-title"),
                rx.text(
                    "Review routed Payment Requests and record approval decisions. "
                    "Every decision is stored as audit evidence.",
                    class_name="wispay-page-lede",
                ),
                class_name="wispay-page-head",
            ),
            _status_banner(),
            _actor_switcher(),
            rx.el.div(
                _queue_table(),
                rx.el.div(
                    _decision_panel(),
                    _timeline_card(),
                    _route_tool(),
                    class_name="wispay-appr-side",
                ),
                class_name="wispay-appr-layout",
            ),
            class_name="wispay-page",
        )
    )
