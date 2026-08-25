"""Reusable WisPay visual styles for Reflex components.

Import the public namespaces from this module instead of repeating visual values
inside pages and components::

    from WisPay.styles import Animations, Classes, Styles

    rx.box(
        rx.heading("Payment Requests"),
        class_name=Classes.PAGE,
        style=Styles.page,
    )

The values are backed by ``assets/design-tokens.css`` and the visual contract in
``DESIGN.md``. Keep component selection and API usage aligned with the current
Buridan UI catalog: https://buridan-ui.reflex.run/llms.txt
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx


class Tokens:
    """Namespaced CSS-token references for inline Reflex styles."""

    BG: ClassVar[str] = "var(--ws-bg)"
    SURFACE: ClassVar[str] = "var(--ws-surface)"
    SURFACE_WARM: ClassVar[str] = "var(--ws-surface-warm)"
    FG: ClassVar[str] = "var(--ws-fg)"
    FG_2: ClassVar[str] = "var(--ws-fg-2)"
    MUTED: ClassVar[str] = "var(--ws-muted)"
    BORDER: ClassVar[str] = "var(--ws-border)"
    BORDER_SOFT: ClassVar[str] = "var(--ws-border-soft)"
    ACCENT: ClassVar[str] = "var(--ws-accent)"
    ACCENT_HOVER: ClassVar[str] = "var(--ws-accent-hover)"
    ACCENT_ACTIVE: ClassVar[str] = "var(--ws-accent-active)"
    ACCENT_ON: ClassVar[str] = "var(--ws-accent-on)"
    SUCCESS: ClassVar[str] = "var(--ws-success)"
    WARN: ClassVar[str] = "var(--ws-warn)"
    DANGER: ClassVar[str] = "var(--ws-danger)"
    FONT_DISPLAY: ClassVar[str] = "var(--ws-font-display)"
    FONT_BODY: ClassVar[str] = "var(--ws-font-body)"
    FONT_MONO: ClassVar[str] = "var(--ws-font-mono)"
    FOCUS_RING: ClassVar[str] = "var(--ws-focus-ring)"
    ELEV_RING: ClassVar[str] = "var(--ws-elev-ring)"
    ELEV_RAISED: ClassVar[str] = "var(--ws-elev-raised)"
    EASE_STANDARD: ClassVar[str] = "var(--ws-ease-standard)"
    MOTION_FAST: ClassVar[str] = "var(--ws-motion-fast)"
    MOTION_BASE: ClassVar[str] = "var(--ws-motion-base)"


class Animations:
    """Animation and transition values backed by global keyframes."""

    PAGE_ENTER: ClassVar[str] = "wispay-page-in var(--ws-motion-base) var(--ws-ease-standard) both"
    TOAST_IN: ClassVar[str] = "wispay-toast-in var(--ws-motion-base) var(--ws-ease-standard) both"
    SKELETON: ClassVar[str] = "wispay-shimmer 1.1s linear infinite"
    HOVER_TRANSITION: ClassVar[str] = (
        "background-color var(--ws-motion-fast) var(--ws-ease-standard), "
        "box-shadow var(--ws-motion-fast) var(--ws-ease-standard), "
        "transform 80ms ease"
    )
    SURFACE_TRANSITION: ClassVar[str] = (
        "background-color var(--ws-motion-fast) var(--ws-ease-standard), "
        "color var(--ws-motion-fast) var(--ws-ease-standard)"
    )


class Classes:
    """Class names for shared CSS behavior and motion."""

    DESIGN_SCOPE: ClassVar[str] = "wispay-design-scope"
    PAGE: ClassVar[str] = "wispay-page"
    TOAST: ClassVar[str] = "wispay-toast"
    SKELETON: ClassVar[str] = "wispay-skeleton"


class Styles:
    """Reusable ``rx.Style`` values for common WisPay surfaces."""

    root: ClassVar[rx.Style] = rx.Style(
        {
            "background_color": Tokens.BG,
            "color": Tokens.FG,
            "font_family": Tokens.FONT_BODY,
            "font_size": "16px",
            "line_height": "1.5",
            "letter_spacing": "0.16px",
        }
    )
    container: ClassVar[rx.Style] = rx.Style(
        {
            "width": "100%",
            "max_width": "var(--ws-container-max)",
            "margin": "0 auto",
            "padding_left": "var(--ws-container-gutter-desktop)",
            "padding_right": "var(--ws-container-gutter-desktop)",
        }
    )
    page: ClassVar[rx.Style] = rx.Style(
        {
            "min_height": "100vh",
            "background_color": Tokens.BG,
            "color": Tokens.FG,
            "animation": Animations.PAGE_ENTER,
        }
    )
    display_heading: ClassVar[rx.Style] = rx.Style(
        {
            "font_family": Tokens.FONT_DISPLAY,
            "font_weight": "300",
            "line_height": "1.08",
            "letter_spacing": "-0.02em",
            "color": Tokens.FG,
        }
    )
    meta: ClassVar[rx.Style] = rx.Style(
        {
            "font_family": Tokens.FONT_MONO,
            "font_size": "12px",
            "letter_spacing": "0.02em",
            "color": Tokens.MUTED,
        }
    )
    card: ClassVar[rx.Style] = rx.Style(
        {
            "background_color": Tokens.BG,
            "border_radius": "var(--ws-radius-md)",
            "box_shadow": Tokens.ELEV_RING,
            "padding": "var(--ws-space-6)",
        }
    )
    card_inset: ClassVar[rx.Style] = rx.Style(
        {
            "background_color": Tokens.SURFACE,
            "border_radius": "var(--ws-radius-md)",
            "padding": "var(--ws-space-5)",
        }
    )
    card_warm: ClassVar[rx.Style] = rx.Style(
        {
            "background_color": Tokens.SURFACE_WARM,
            "border_radius": "var(--ws-radius-lg)",
            "box_shadow": "rgba(78, 50, 23, 0.04) 0 6px 16px, rgba(0, 0, 0, 0.04) 0 0 0 1px",
            "padding": "var(--ws-space-6)",
        }
    )
    button_primary: ClassVar[rx.Style] = rx.Style(
        {
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "min_height": "44px",
            "padding_left": "18px",
            "padding_right": "18px",
            "border": "1px solid transparent",
            "border_radius": "var(--ws-radius-pill)",
            "background_color": Tokens.ACCENT,
            "color": Tokens.ACCENT_ON,
            "font_family": Tokens.FONT_BODY,
            "font_size": "15px",
            "font_weight": "500",
            "cursor": "pointer",
            "transition": Animations.HOVER_TRANSITION,
            "_hover": {"background_color": Tokens.ACCENT_HOVER},
            "_active": {"background_color": Tokens.ACCENT_ACTIVE, "transform": "translateY(1px)"},
            "_focus": {"outline": "none", "box_shadow": Tokens.FOCUS_RING},
            "_disabled": {"cursor": "not-allowed", "opacity": "0.45"},
        }
    )
    button_secondary: ClassVar[rx.Style] = rx.Style(
        {
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "min_height": "44px",
            "padding_left": "18px",
            "padding_right": "18px",
            "border": "1px solid transparent",
            "border_radius": "var(--ws-radius-pill)",
            "background_color": Tokens.BG,
            "color": Tokens.FG,
            "font_family": Tokens.FONT_BODY,
            "font_size": "15px",
            "font_weight": "500",
            "cursor": "pointer",
            "box_shadow": Tokens.ELEV_RAISED,
            "transition": Animations.HOVER_TRANSITION,
            "_hover": {"box_shadow": Tokens.ELEV_RING},
            "_active": {"transform": "translateY(1px)"},
            "_focus": {"outline": "none", "box_shadow": Tokens.FOCUS_RING},
            "_disabled": {"cursor": "not-allowed", "opacity": "0.45"},
        }
    )
    button_ghost: ClassVar[rx.Style] = rx.Style(
        {
            "display": "inline-flex",
            "align_items": "center",
            "justify_content": "center",
            "min_height": "44px",
            "padding_left": "14px",
            "padding_right": "14px",
            "border": "1px solid transparent",
            "border_radius": "var(--ws-radius-pill)",
            "background_color": "transparent",
            "color": Tokens.FG_2,
            "font_family": Tokens.FONT_BODY,
            "font_size": "15px",
            "cursor": "pointer",
            "transition": Animations.SURFACE_TRANSITION,
            "_hover": {"background_color": Tokens.SURFACE, "color": Tokens.FG},
            "_focus": {"outline": "none", "box_shadow": Tokens.FOCUS_RING},
        }
    )
    button_danger_ghost: ClassVar[rx.Style] = rx.Style(
        {
            **button_ghost,
            "color": Tokens.DANGER,
            "_hover": {"background_color": "color-mix(in oklch, var(--ws-danger) 7%, transparent)"},
        }
    )
    field: ClassVar[rx.Style] = rx.Style(
        {
            "display": "flex",
            "flex_direction": "column",
            "gap": "var(--ws-space-2)",
        }
    )
    label: ClassVar[rx.Style] = rx.Style(
        {
            "color": Tokens.FG_2,
            "font_family": Tokens.FONT_BODY,
            "font_size": "12px",
            "font_weight": "500",
            "letter_spacing": "0.03em",
        }
    )
    input: ClassVar[rx.Style] = rx.Style(
        {
            "width": "100%",
            "min_height": "44px",
            "padding": "10px 14px",
            "border": "0",
            "border_radius": "var(--ws-radius-sm)",
            "background_color": Tokens.SURFACE,
            "color": Tokens.FG,
            "font_family": Tokens.FONT_BODY,
            "font_size": "15px",
            "box_shadow": "rgba(0, 0, 0, 0.075) 0 0 0 0.5px inset, rgba(0, 0, 0, 0.05) 0 0 0 1px inset",
            "transition": "box-shadow var(--ws-motion-fast) var(--ws-ease-standard)",
            "_focus": {"outline": "none", "box_shadow": Tokens.FOCUS_RING},
            "_disabled": {"cursor": "not-allowed", "opacity": "0.45"},
        }
    )
    status_pill: ClassVar[rx.Style] = rx.Style(
        {
            "display": "inline-flex",
            "align_items": "center",
            "gap": "7px",
            "padding": "5px 12px",
            "border_radius": "var(--ws-radius-pill)",
            "background_color": Tokens.SURFACE,
            "color": Tokens.FG_2,
            "font_family": Tokens.FONT_BODY,
            "font_size": "12px",
            "font_weight": "500",
        }
    )
    table: ClassVar[rx.Style] = rx.Style(
        {
            "width": "100%",
            "border_collapse": "collapse",
            "font_family": Tokens.FONT_BODY,
            "font_size": "14px",
            "color": Tokens.FG,
        }
    )
    number: ClassVar[rx.Style] = rx.Style(
        {
            "font_family": Tokens.FONT_MONO,
            "font_variant_numeric": "tabular-nums",
            "letter_spacing": "0",
            "white_space": "nowrap",
        }
    )


__all__ = ["Animations", "Classes", "Styles", "Tokens"]
