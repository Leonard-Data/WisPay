"""Top navigation for the WisPay application shell."""

from __future__ import annotations

import reflex as rx

from states.auth_state import AuthState
from states.base_state import BaseState


def navbar(page_title: str, section: str = "Workspace") -> rx.Component:
    """Render the desktop context bar and mobile navigation bar."""
    return rx.el.header(
        rx.button(
            rx.cond(
                BaseState.is_collapsed,
                rx.icon("chevrons-right", size=18),
                rx.icon("chevrons-left", size=18),
            ),
            aria_label="Toggle sidebar",
            title="Toggle sidebar",
            class_name="wispay-icon-button wispay-sidebar-toggle",
            on_click=BaseState.toggle_sidebar_collapsed,
        ),
        rx.button(
            rx.icon("menu", size=20),
            aria_label=rx.cond(BaseState.sidebar_open, "Close navigation", "Open navigation"),
            title=rx.cond(BaseState.sidebar_open, "Close navigation", "Open navigation"),
            class_name="wispay-icon-button wispay-mobile-menu",
            on_click=BaseState.toggle_sidebar,
        ),
        rx.link(
            rx.image(
                src="/brand-mark.svg",
                alt="WisPay mark",
                class_name="wispay-brand-mark",
            ),
            rx.text("WisPay", class_name="wispay-brand-wordmark"),
            href="/",
            class_name="wispay-mobile-brand",
            on_click=BaseState.close_sidebar,
        ),
        rx.box(
            rx.text(section, class_name="wispay-navbar-section"),
            rx.text(page_title, class_name="wispay-navbar-title"),
            class_name="wispay-navbar-context",
        ),
        rx.box(
            rx.button(
                rx.icon("bell", size=18),
                aria_label="Notifications are not connected yet",
                title="Notifications are not connected yet",
                disabled=True,
                class_name="wispay-icon-button",
            ),
            rx.color_mode.button(
                aria_label="Toggle light and dark mode",
                title="Toggle light and dark mode",
                class_name="wispay-icon-button",
            ),
            rx.cond(
                AuthState.is_authenticated,
                rx.box(
                    rx.box("WP", class_name="wispay-navbar-avatar"),
                    rx.vstack(
                        rx.text(AuthState.current_user_name, class_name="wispay-navbar-workspace"),
                        rx.text(
                            AuthState.current_user_email, class_name="wispay-navbar-user-email"
                        ),
                        align_items="start",
                        spacing="0",
                    ),
                    title=AuthState.current_roles_label,
                    class_name="wispay-navbar-session",
                ),
                rx.link("Sign in", href="/login", class_name="wispay-navbar-signin"),
            ),
            rx.cond(
                AuthState.is_authenticated,
                rx.button(
                    "Sign out",
                    aria_label="Sign out of WisPay",
                    class_name="wispay-button wispay-new-button-ghost wispay-navbar-signout",
                    on_click=AuthState.initiate_logout,
                ),
            ),
            class_name="wispay-navbar-actions",
        ),
        class_name="wispay-navbar",
    )
