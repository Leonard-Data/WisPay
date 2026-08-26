"""Callback page completing the Entra ID authorization-code redirect.

Public surface: a chrome-free spinner while ``AuthState.handle_callback``
validates state, exchanges the code, and opens the server-side session.
"""

from __future__ import annotations

import reflex as rx

from WisPay.components.auth_layout import auth_page, auth_spinner


def callback_page() -> rx.Component:
    """Render the /auth/callback transition page with its on_load handler."""
    return auth_page(
        rx.el.div(
            auth_spinner("Completing sign-in…"),
        )
    )
