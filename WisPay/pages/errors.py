"""Standalone error pages for expected application and server failures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from WisPay.layout.general import general_error_page

if TYPE_CHECKING:
    import reflex as rx


def not_found_page() -> rx.Component:
    """Render the 404 page."""
    return general_error_page(404)


def server_error_page() -> rx.Component:
    """Render the 500 page."""
    return general_error_page(500)


def unavailable_page() -> rx.Component:
    """Render the 503 page."""
    return general_error_page(503)


__all__ = ["not_found_page", "server_error_page", "unavailable_page"]
