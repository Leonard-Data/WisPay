"""Access-request ("sign up") page for WisPay.

Public surface: collects work email, name, business unit, and justification,
then records a Pending access request through ``states.access_request`` and
``WisPay.services.user_context``. This page never implies immediate access;
activation and role assignment are administrative actions (ADR-0007).
"""

from __future__ import annotations

import reflex as rx

from states.access_request import AccessRequestState
from WisPay.components.auth_layout import (
    auth_actions,
    auth_banner,
    auth_brand_mark,
    auth_card,
    auth_heading,
    auth_lede,
    auth_page,
)
from WisPay.components.form_fields import form_field


def back_to_sign_in_link() -> rx.Component:
    """Render the ghost link returning to the sign-in page."""

    return rx.link(
        "Back to sign in",
        href="/login",
        class_name="wispay-button wispay-new-button-ghost",
        style={"width": "100%"},
    )


def signup_form() -> rx.Component:
    """Render the access-request form fields and submit action."""

    return rx.el.div(
        form_field(
            "Work email",
            rx.el.input(
                placeholder="you@company.com",
                value=AccessRequestState.email,
                on_change=AccessRequestState.set_email,
                type_="email",
                autocomplete="email",
                class_name="wispay-new-input",
            ),
        ),
        form_field(
            "Full name",
            rx.el.input(
                placeholder="Full name",
                value=AccessRequestState.full_name,
                on_change=AccessRequestState.set_full_name,
                class_name="wispay-new-input",
            ),
        ),
        form_field(
            "Business unit",
            rx.el.input(
                placeholder="Team or department",
                value=AccessRequestState.business_unit,
                on_change=AccessRequestState.set_business_unit,
                class_name="wispay-new-input",
            ),
        ),
        form_field(
            "Justification",
            rx.el.textarea(
                placeholder="What payment-request work needs portal access?",
                value=AccessRequestState.justification,
                on_change=AccessRequestState.set_justification,
                rows=3,
                class_name="wispay-new-textarea",
            ),
        ),
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "var(--ws-space-4)",
            "width": "100%",
            "text_align": "left",
        },
    )


def submitted_notice() -> rx.Component:
    """Render the post-submission explanation instead of the form."""

    return rx.el.div(
        rx.el.div(
            rx.text("Request recorded", class_name="wispay-card-kicker"),
            rx.text(
                "A WisPay administrator reviews access requests and assigns "
                "roles. You can sign in with your corporate account once your "
                "access is activated.",
                class_name="wispay-card-copy",
            ),
            class_name="wispay-card wispay-card-inset",
        ),
        style={
            "display": "flex",
            "flex_direction": "column",
            "gap": "var(--ws-space-3)",
            "width": "100%",
        },
    )


def signup_page() -> rx.Component:
    """Render the /signup page: form while pending, notice after submission."""

    return auth_page(
        auth_card(
            auth_brand_mark(),
            auth_heading("Request access"),
            auth_lede(
                "Ask a WisPay administrator to activate portal access for your corporate account."
            ),
            auth_banner(AccessRequestState.form_error),
            rx.cond(
                AccessRequestState.submitted,
                submitted_notice(),
                rx.fragment(
                    signup_form(),
                    auth_actions(
                        rx.button(
                            "Submit request",
                            class_name="wispay-button wispay-button-primary",
                            style={"width": "100%"},
                            on_click=AccessRequestState.submit_request,
                        ),
                    ),
                ),
            ),
            back_to_sign_in_link(),
        )
    )
