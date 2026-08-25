"""WisPay Reflex application entry point."""

import reflex as rx

from WisPay.routers import register_routes


class State(rx.State):
    """Root application state; feature-specific state lives in substates."""


app = rx.App(stylesheets=["design-tokens.css", "layout.css", "globals.css"])
register_routes(app)
