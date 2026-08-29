"""Toast component for non-blocking feedback.

A dark pill with white text, the source ``wispay-toast-in`` animation, and a
danger variant for error toasts (per ``DESIGN.md#Dialogs, toasts, empty and
loading states``). Toasts are rendered through a bound state var so the same
component handles all flavors and disappears when the state resets.

Usage::

    from WisPay.components.toast import toast, ToastTone

    toast("External reference recorded.", tone=ToastTone.SUCCESS)
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx

from WisPay.styles import Animations, Classes, Tokens


class ToastTone:
    """Tone identifiers for toasts."""

    NEUTRAL: ClassVar[str] = "neutral"
    SUCCESS: ClassVar[str] = "success"
    DANGER: ClassVar[str] = "danger"


_TOAST_STYLE: rx.Style = rx.Style(
    {
        "position": "fixed",
        "right": "var(--ws-space-6)",
        "bottom": "var(--ws-space-6)",
        "z_index": 60,
        "display": "inline-flex",
        "align_items": "center",
        "gap": "var(--ws-space-3)",
        "padding": "12px 18px",
        "border_radius": "var(--ws-radius-md)",
        "background_color": Tokens.FG,
        "color": Tokens.BG,
        "font_family": Tokens.FONT_BODY,
        "font_size": "13px",
        "box_shadow": Tokens.ELEV_RING,
        "animation": Animations.TOAST_IN,
    }
)


def toast(
    message: rx.Var[str] | str,
    *,
    tone: str = ToastTone.NEUTRAL,
) -> rx.Component:
    """Render a single toast pill that disappears when ``message`` is empty.

    Args:
        message: Toast copy; when empty the toast renders nothing.
        tone: ``ToastTone`` value; defaults to neutral.

    Usage::

        toast("External reference recorded.", tone=ToastTone.SUCCESS)
    """

    is_danger = tone == ToastTone.DANGER
    is_success = tone == ToastTone.SUCCESS
    return rx.cond(
        message != "",
        rx.el.div(
            rx.el.span(class_name="wispay-toast-dot"),
            message,
            role="status",
            aria_live="polite",
            class_name=Classes.TOAST,
            style={
                **_TOAST_STYLE,
                "background_color": rx.cond(
                    is_danger,
                    Tokens.DANGER,
                    rx.cond(is_success, Tokens.SUCCESS, Tokens.FG),
                ),
            },
        ),
        rx.fragment(),
    )


__all__ = [
    "ToastTone",
    "toast",
]
