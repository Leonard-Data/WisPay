"""Empty, loading, and error state components for WisPay queues and pages.

Each surface renders an icon plus a short title and copy, with one
single next step (link or button). Loading uses the source shimmer; error
uses the danger banner tone.

Usage::

    from WisPay.components.empty_state import empty_state, loading_state, error_state

    empty_state(
        title="No approvals are waiting on you",
        copy="When a submitted request routes to your queue, it appears here.",
        action_label="View requests",
        action_href="/requests",
    )
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx


class EmptyIcon:
    """Icon identifiers for the empty state component."""

    INBOX: ClassVar[str] = "inbox"
    SEARCH: ClassVar[str] = "search-x"
    FOLDER: ClassVar[str] = "folder"
    CHECK: ClassVar[str] = "check-check"
    WALLET: ClassVar[str] = "wallet"
    HISTORY: ClassVar[str] = "history"
    CLIPBOARD: ClassVar[str] = "clipboard"
    RECEIPT: ClassVar[str] = "receipt"
    SCROLL: ClassVar[str] = "scroll-text"


def empty_state(
    *,
    title: str | rx.Var[str],
    copy: str | rx.Var[str],
    action_label: str = "",
    action_href: str = "",
    action_click: object | None = None,
    icon: str = EmptyIcon.INBOX,
) -> rx.Component:
    """Render an empty-state panel with one clear next step.

    Args:
        title: Short headline (sentence case).
        copy: One sentence of explanatory copy.
        action_label: Optional primary action label.
        action_href: Link target for the action.
        action_click: Optional click handler (alternative to ``action_href``).
        icon: ``EmptyIcon`` value; defaults to inbox.

    Usage::

        empty_state(
            title="No requests yet",
            copy="Start by creating a new payment request.",
            action_label="New Payment Request",
            action_href="/requests/new",
        )
    """

    action: rx.Component | None = None
    if action_label:
        if action_click is not None:
            action = rx.el.button(
                action_label,
                type="button",
                on_click=action_click,
                class_name="wispay-button wispay-button-primary",
            )
        elif action_href:
            action = rx.link(
                action_label,
                href=action_href,
                class_name="wispay-button wispay-button-primary",
            )

    children: list[rx.Component] = [
        rx.icon(icon, size=28, class_name="wispay-empty-icon", aria_hidden=True),
        rx.el.p(title, class_name="wispay-empty-title"),
        rx.el.p(copy, class_name="wispay-empty-copy"),
    ]
    if action is not None:
        children.append(action)
    return rx.el.div(*children, class_name="wispay-request-empty")


def loading_state(*, label: str = "Loading…") -> rx.Component:
    """Render a loading skeleton with the source shimmer keyframe.

    Args:
        label: Accessible label for the loading region.

    Usage::

        loading_state(label="Loading payment requests")
    """

    return rx.el.div(
        rx.el.div(class_name="wispay-skeleton wispay-skeleton-line"),
        rx.el.div(class_name="wispay-skeleton wispay-skeleton-line is-short"),
        rx.el.div(class_name="wispay-skeleton wispay-skeleton-line is-medium"),
        role="status",
        aria_label=label,
        aria_live="polite",
        class_name="wispay-skeleton-stack",
    )


def error_state(
    *,
    title: str = "Something went wrong",
    copy: str | rx.Var[str] = "",
    action_label: str = "Return to dashboard",
    action_href: str = "/",
) -> rx.Component:
    """Render an error state with one safe exit action.

    Args:
        title: Short headline.
        copy: One sentence of detail.
        action_label: Primary action label.
        action_href: Primary action link target.

    Usage::

        error_state(
            title="Could not load your requests",
            copy=state.load_error,
        )
    """

    return rx.el.div(
        rx.el.div(
            rx.el.p(title, class_name="wispay-error-state-title"),
            rx.el.p(copy, class_name="wispay-error-state-copy"),
            rx.link(
                rx.icon("arrow-left", size=16),
                action_label,
                href=action_href,
                class_name="wispay-button wispay-button-secondary",
            ),
            class_name="wispay-error-state",
        ),
        role="alert",
        class_name="wispay-error-state-wrap",
    )


__all__ = [
    "EmptyIcon",
    "empty_state",
    "error_state",
    "loading_state",
]
