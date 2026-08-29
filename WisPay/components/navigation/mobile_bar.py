"""Mobile navigation bar — menu, language chip, notifications, and brand.

Sits below ``1024px`` (the sidebar drawer breakpoint). Exposed as a
``rx.el.div`` so it can render inside or outside the application shell.

Usage::

    from WisPay.components.navigation.mobile_bar import mobile_bar

    mobile_bar(page_title="Requests", section="Workspace")
"""

from __future__ import annotations

import reflex as rx

from states.base_state import BaseState


def _menu_button() -> rx.Component:
    """Render the responsive menu toggle button."""

    return rx.button(
        rx.icon("menu", size=20),
        aria_label=rx.cond(BaseState.sidebar_open, "Close navigation", "Open navigation"),
        title=rx.cond(BaseState.sidebar_open, "Close navigation", "Open navigation"),
        class_name="wispay-icon-button wispay-mobile-menu",
        on_click=BaseState.toggle_sidebar,
        type="button",
    )


def _brand_link() -> rx.Component:
    """Render the brand-mark + wordmark for the mobile bar."""

    return rx.link(
        rx.image(
            src="/brand-mark.svg",
            alt="WisPay mark",
            class_name="wispay-brand-mark",
        ),
        rx.text("WisPay", class_name="wispay-brand-wordmark"),
        href="/",
        class_name="wispay-mobile-brand",
        on_click=BaseState.close_sidebar,
    )


def _language_chip() -> rx.Component:
    """Render the language chip used for the EN/VI toggle."""

    return rx.button(
        "EN",
        rx.icon("languages", size=14),
        aria_label="Switch language",
        title="Switch language",
        class_name="wispay-mobile-langchip",
        type="button",
    )


def _notifications_button() -> rx.Component:
    """Render the notification icon button (placeholder state for now)."""

    return rx.button(
        rx.icon("bell", size=18),
        aria_label="Notifications",
        title="Notifications",
        class_name="wispay-icon-button wispay-mobile-notifications",
        type="button",
        disabled=True,
    )


def mobile_bar(page_title: str, section: str = "Workspace") -> rx.Component:
    """Render the bottom-aligned mobile navigation bar.

    Args:
        page_title: Display title shown in the contextual region.
        section: Section context (eyebrow label).

    Usage::

        mobile_bar("Requests", section="Workspace")
    """

    return rx.el.div(
        _menu_button(),
        _brand_link(),
        rx.el.div(
            rx.el.span(section, class_name="wispay-mobile-section"),
            rx.el.span(page_title, class_name="wispay-mobile-title"),
            class_name="wispay-mobile-context",
        ),
        rx.el.div(
            _language_chip(),
            _notifications_button(),
            class_name="wispay-mobile-actions",
        ),
        aria_label="Mobile navigation",
        class_name="wispay-mobile-bar",
    )


__all__ = ["mobile_bar"]
