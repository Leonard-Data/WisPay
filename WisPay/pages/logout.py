"""Sign-out transition page for WisPay.

Public surface: closes the server-side session via ``AuthState.initiate_logout``
during the page load. The Entra ID end-session round trip lands with the
production identity slice; see ``states/auth_state`` docstring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from WisPay.components.auth_layout import auth_page, auth_spinner

if TYPE_CHECKING:
    import reflex as rx


def logout_page() -> rx.Component:
    """Render the /logout transition card that clears the session."""
    return auth_page(auth_spinner("Signing out…"))
