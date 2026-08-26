"""Page composition for ``/requests/new``.

Owns the wizard chrome — progress step bar, back/continue actions, the
submitted confirmation panel, and the page header — and composes the four
step panels from sibling modules.

Usage::

    from WisPay.pages.request_new import request_new_page

    request_new_page()
"""

from __future__ import annotations

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.layout.shell import shell
from WisPay.pages.request_new.catalogs import STEPS
from WisPay.pages.request_new.step_details import step_details
from WisPay.pages.request_new.step_documents import step_documents
from WisPay.pages.request_new.step_review import step_review
from WisPay.pages.request_new.step_type import step_type


def step_bar() -> rx.Component:
    """Render the four-step progress bar with jump-to-step buttons.

    Usage::
        step_bar()
    """

    buttons: list[rx.Component] = []
    for index, label in enumerate(STEPS, start=1):
        buttons.append(
            rx.el.button(
                rx.el.span(str(index), class_name="wispay-new-step-num"),
                rx.el.span(label),
                type="button",
                class_name=rx.cond(
                    RequestCreateState.step == index,
                    "wispay-new-step is-active",
                    rx.cond(
                        RequestCreateState.step > index,
                        "wispay-new-step is-done",
                        "wispay-new-step is-future",
                    ),
                ),
                aria_current=rx.cond(RequestCreateState.step == index, "step", ""),
                on_click=lambda idx=index: RequestCreateState.go_to_step(idx),  # type: ignore[operator]
                key=f"wispay-new-step-{index}",
            )
        )
    return rx.el.div(
        *buttons, role="group", aria_label="Request progress", class_name="wispay-new-steps"
    )


def wizard_actions() -> rx.Component:
    """Render the Back / Continue / Submit action row for the active step.

    Usage::
        wizard_actions()
    """

    return rx.el.div(
        rx.cond(
            RequestCreateState.step > 1,
            rx.el.button(
                "Back",
                type="button",
                class_name="wispay-button wispay-new-button-ghost",
                on_click=RequestCreateState.go_back,
            ),
            rx.el.span(aria_hidden="true"),
        ),
        rx.cond(
            RequestCreateState.step < 4,
            rx.el.button(
                "Continue",
                type="button",
                class_name="wispay-button wispay-button-primary",
                on_click=RequestCreateState.go_next,
            ),
            rx.el.button(
                "Submit for approval",
                type="button",
                class_name="wispay-button wispay-button-primary",
                on_click=RequestCreateState.submit,
            ),
        ),
        class_name="wispay-new-actions",
    )


def success_panel() -> rx.Component:
    """Render the post-submission confirmation panel.

    Usage::
        rx.cond(RequestCreateState.submitted_number != "", success_panel(), ...)
    """

    return rx.el.section(
        rx.el.p("Submitted", class_name="wispay-new-eyebrow"),
        rx.el.h2("Payment Request submitted", class_name="wispay-new-h2"),
        rx.el.p(
            "Your request entered the review lifecycle. Track progress from the queue.",
            class_name="wispay-new-muted",
        ),
        rx.el.span(
            RequestCreateState.submitted_number,
            class_name="wispay-new-num wispay-new-request-number",
        ),
        rx.el.span("Submitted", class_name="wispay-new-pill-success"),
        rx.el.div(
            rx.link(
                "View requests", href="/requests", class_name="wispay-button wispay-button-primary"
            ),
            rx.el.button(
                "Create another",
                type="button",
                class_name="wispay-button wispay-new-button-ghost",
                on_click=RequestCreateState.reset_wizard,
            ),
            class_name="wispay-new-inline-actions",
        ),
        role="status",
        class_name="wispay-new-panel wispay-new-success",
    )


def wizard_header() -> rx.Component:
    """Render the page header copy and draft badge.

    Usage::
        wizard_header()
    """

    return rx.el.header(
        rx.el.div(
            rx.el.p("Request intake", class_name="wispay-new-eyebrow"),
            rx.el.h1("Create payment request", class_name="wispay-new-title"),
            rx.el.p(
                "Build a complete request and submit it for review.",
                class_name="wispay-new-muted",
            ),
            class_name="wispay-new-header-copy",
        ),
        rx.el.span("Draft", class_name="wispay-new-draft-badge"),
        class_name="wispay-new-header",
    )


def live_status() -> rx.Component:
    """Render the polite live region echoing state status messages.

    Usage::
        live_status()
    """

    return rx.el.div(
        RequestCreateState.status_message,
        role="status",
        class_name="wispay-new-live-status",
    )


def active_step_panel() -> rx.Component:
    """Render the step panel matching the current wizard position.

    Usage::
        active_step_panel()
    """

    return rx.cond(
        RequestCreateState.step == 1,
        step_type(),
        rx.cond(
            RequestCreateState.step == 2,
            step_details(),
            rx.cond(RequestCreateState.step == 3, step_documents(), step_review()),
        ),
    )


def request_new_page() -> rx.Component:
    """Render the four-step create-payment-request wizard."""

    return shell(
        rx.el.div(
            wizard_header(),
            live_status(),
            step_bar(),
            rx.cond(
                RequestCreateState.submitted_number != "",
                success_panel(),
                rx.fragment(
                    active_step_panel(),
                    wizard_actions(),
                ),
            ),
            class_name="wispay-new-shell",
        )
    )
