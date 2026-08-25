"""WisPay application navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import reflex as rx

from states.base_state import BaseState

if TYPE_CHECKING:
    from reflex.event import EventHandler


@dataclass(frozen=True, slots=True)
class NavItem:
    """A navigable item in the application shell."""

    label: str
    href: str
    icon: str


@dataclass(frozen=True, slots=True)
class NavGroup:
    """A labelled group of navigation items."""

    label: str
    items: tuple[NavItem, ...]


NAV_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        label="Workspace",
        items=(
            NavItem("Dashboard", "/", "layout-dashboard"),
            NavItem("Requests", "/requests", "inbox"),
            NavItem("New Request", "/requests/new", "file-plus-2"),
        ),
    ),
    NavGroup(
        label="Review",
        items=(
            NavItem("Approvals", "/approvals", "check-check"),
            NavItem("Finance Review", "/finance-review", "clipboard-check"),
        ),
    ),
    NavGroup(
        label="Operations",
        items=(NavItem("Payments", "/payments", "wallet-cards"),),
    ),
    NavGroup(
        label="Governance",
        items=(NavItem("Audit", "/audit", "history"),),
    ),
)


def _nav_item(item: NavItem, active_route: str | None) -> rx.Component:
    """Render one accessible navigation link."""
    is_active = item.href == active_route
    class_name = "wispay-nav-item"
    if is_active:
        class_name += " is-active"

    return rx.link(
        rx.icon(item.icon, size=18),
        rx.text(item.label, class_name="wispay-nav-item-label"),
        # width="100%",
        href=item.href,
        title=item.label,
        class_name=class_name,
        aria_current="page" if is_active else None,
        on_click=BaseState.close_sidebar,
    )


def _group_open_state(label: str) -> bool:
    """Return the state variable controlling one navigation group."""
    if label == "Workspace":
        return BaseState.workspace_group_open
    if label == "Review":
        return BaseState.review_group_open
    if label == "Operations":
        return BaseState.operations_group_open
    if label == "Governance":
        return BaseState.governance_group_open
    raise ValueError(f"Unknown navigation group: {label}")


def _group_toggle_event(label: str) -> EventHandler:
    """Return the event handler controlling one navigation group."""
    if label == "Workspace":
        return cast("EventHandler", BaseState.toggle_workspace_group)
    if label == "Review":
        return cast("EventHandler", BaseState.toggle_review_group)
    if label == "Operations":
        return cast("EventHandler", BaseState.toggle_operations_group)
    if label == "Governance":
        return cast("EventHandler", BaseState.toggle_governance_group)
    raise ValueError(f"Unknown navigation group: {label}")


def _nav_group(group: NavGroup, active_route: str | None) -> rx.Component:
    """Render a collapsible navigation group with a tree-line connector."""
    is_open = _group_open_state(group.label)
    return rx.box(
        rx.button(
            rx.text(group.label, class_name="wispay-nav-label"),
            rx.cond(
                is_open,
                rx.icon("chevron-down", size=14),
                rx.icon("chevron-right", size=14),
            ),
            aria_expanded=is_open,
            aria_label=f"Toggle {group.label} navigation group",
            class_name="wispay-nav-group-toggle",
            on_click=_group_toggle_event(group.label),
        ),
        rx.vstack(
            *[_nav_item(item, active_route) for item in group.items],
            spacing="1",
            width="95%",
            align="stretch",
            class_name=rx.cond(
                is_open,
                "wispay-nav-group-items",
                "wispay-nav-group-items is-hidden",
            ),
        ),
        class_name="wispay-nav-group",
    )


def sidebar(active_route: str | None = None) -> rx.Component:
    """Render the persistent desktop rail and responsive navigation drawer."""
    groups = [_nav_group(group, active_route) for group in NAV_GROUPS]

    return rx.el.aside(
        rx.box(
            rx.link(
                rx.image(
                    src="/brand-mark.svg",
                    alt="WisPay mark",
                    class_name="wispay-brand-mark",
                ),
                rx.text("WisPay", class_name="wispay-brand-wordmark"),
                href="/",
                class_name="wispay-brand",
                on_click=BaseState.close_sidebar,
            ),
            rx.text("Internal request-to-pay workspace", class_name="wispay-build-label"),
            class_name="wispay-sidebar-header",
        ),
        rx.box(
            rx.el.nav(
                *groups,
                aria_label="Primary navigation",
                class_name="wispay-sidebar-scroll",
            ),
            class_name="wispay-sidebar-body",
        ),
        rx.box(
            rx.text("Current workspace", class_name="wispay-nav-label"),
            rx.box(
                rx.box("WP", class_name="wispay-workspace-avatar"),
                rx.box(
                    rx.text("WisPay portal", class_name="wispay-workspace-name"),
                    rx.text("Session context", class_name="wispay-workspace-meta"),
                    class_name="wispay-workspace-copy",
                ),
                class_name="wispay-workspace-card",
            ),
            class_name="wispay-sidebar-footer",
        ),
        class_name=rx.cond(
            BaseState.is_collapsed,
            rx.cond(
                BaseState.sidebar_open,
                "wispay-sidebar is-collapsed is-open",
                "wispay-sidebar is-collapsed",
            ),
            rx.cond(
                BaseState.sidebar_open,
                "wispay-sidebar is-open",
                "wispay-sidebar",
            ),
        ),
    )
