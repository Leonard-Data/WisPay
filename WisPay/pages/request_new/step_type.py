"""Type step (step 1) of the create-payment-request wizard.

Renders the request-type selection cards for supplier and employee
payments; selection routes through ``RequestCreateState.select_type``.

Usage::

    from WisPay.pages.request_new.step_type import step_type

    rx.cond(RequestCreateState.step == 1, step_type(), ...)
"""

from __future__ import annotations

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.pages.request_new.catalogs import EMPLOYEE_TYPES, TYPE_COPY


def type_card(subtype_key: str, label: str, family_key: str) -> rx.Component:
    """Render one selectable request-type card.

    Args:
        subtype_key: Canonical subtype code (e.g. ``"reimbursement"``).
        label: Card title shown to the requester.
        family_key: Request family owning the subtype (``vendor``/``employee``).

    Usage::
        type_card("standard", "Vendor payment", "vendor")
    """

    selected = (RequestCreateState.family == family_key) & (
        RequestCreateState.subtype == subtype_key
    )
    return rx.el.button(
        rx.el.span(label, class_name="wispay-new-type-title"),
        rx.el.span(TYPE_COPY[subtype_key], class_name="wispay-new-type-copy"),
        rx.el.span(rx.cond(selected, "Selected", "Choose"), class_name="wispay-new-type-state"),
        type="button",
        class_name=rx.cond(selected, "wispay-new-type-card is-selected", "wispay-new-type-card"),
        aria_pressed=rx.cond(selected, "true", "false"),
        on_click=RequestCreateState.select_type(family_key, subtype_key),  # type: ignore[operator]
        key=f"type-{subtype_key}",
    )


def step_type() -> rx.Component:
    """Render the full Type step panel with both request families.

    Usage::
        rx.cond(RequestCreateState.step == 1, step_type(), ...)
    """

    return rx.el.section(
        rx.el.p("Step 1 · Request type", class_name="wispay-new-eyebrow"),
        rx.el.h2("What are you requesting?", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p(
            "Choose the route that matches the payment. The next step adapts to your selection.",
            class_name="wispay-new-muted",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.strong("Supplier payments"),
                    rx.el.span("1 option", class_name="wispay-new-meta"),
                    class_name="wispay-new-group-label",
                ),
                rx.el.div(
                    type_card("standard", "Vendor payment", "vendor"),
                    class_name="wispay-new-type-grid is-single",
                ),
                class_name="wispay-new-group",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.strong("Employee payments"),
                    rx.el.span("4 options", class_name="wispay-new-meta"),
                    class_name="wispay-new-group-label",
                ),
                rx.el.div(
                    *[type_card(key, label, "employee") for key, label in EMPLOYEE_TYPES],
                    class_name="wispay-new-type-grid",
                ),
                class_name="wispay-new-group",
            ),
        ),
        class_name="wispay-new-panel",
        id="wizard-step-title",
    )
