"""Shared application shell for WisPay pages."""

from __future__ import annotations

import reflex as rx

from states.base_state import BaseState
from WisPay.components.footer import footer
from WisPay.components.navbar import navbar
from WisPay.components.sidebar import sidebar


def shell(content: rx.Component) -> rx.Component:
    """Wrap page content with the shared WisPay navigation shell."""
    return rx.box(
        sidebar(),
        rx.box(
            navbar(page_title="WisPay", section="Workspace"),
            rx.el.main(content, class_name="wispay-content"),
            footer(),
            class_name=rx.cond(
                BaseState.is_collapsed,
                "wispay-main-frame is-sidebar-collapsed",
                "wispay-main-frame",
            ),
        ),
        rx.box(
            aria_hidden="true",
            class_name=rx.cond(
                BaseState.sidebar_open,
                "wispay-backdrop is-visible",
                "wispay-backdrop",
            ),
            on_click=BaseState.close_sidebar,
        ),
        class_name="wispay-shell",
    )
