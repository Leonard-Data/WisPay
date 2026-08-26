"""Sign-in page for WisPay corporate SSO (Microsoft Entra ID).

Public surface: renders the SSO button bound to ``AuthState.start_login`` and
surfaces configuration or flow errors through the shared danger banner.
"""

from __future__ import annotations

import reflex as rx

from states.auth_state import AuthState
from WisPay.components.auth_layout import (
    auth_actions,
    auth_banner,
    auth_brand_mark,
    auth_card,
    auth_heading,
    auth_lede,
    auth_page,
)


def sign_in_button() -> rx.Component:
    """Render the primary corporate SSO button.

    Crimson primary action per DESIGN; minimum 44px height via
    ``wispay-button``. Bound to ``AuthState.start_login``.

    Usage::
        sign_in_button()
    """
    return rx.button(
        "Sign in with Microsoft",
        class_name="wispay-button wispay-button-primary",
        style={"width": "100%"},
        on_click=AuthState.start_login,
    )


def request_access_link() -> rx.Component:
    """Render the ghost link to the access-request page.

    Usage::
        request_access_link()
    """
    return rx.link(
        "Request access",
        href="/signup",
        class_name="wispay-button wispay-new-button-ghost",
        style={"width": "100%"},
    )


def login_page() -> rx.Component:
    """Render the /login page: brand, heading, error banner, SSO actions."""
    return auth_page(
        auth_card(
            auth_brand_mark(),
            auth_heading("Sign in"),
            auth_lede("WisPay uses your corporate Microsoft account through single sign-on."),
            auth_banner(AuthState.auth_error),
            auth_actions(
                sign_in_button(),
                request_access_link(),
            ),
        )
    )
