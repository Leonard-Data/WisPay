"""Standalone centered layouts for the Entra ID authentication surface.

These layouts render outside the application sidebar shell so that sign-in,
access-request, callback, and logout pages keep a focused, chrome-free frame.
All visual values come from ``WisPay.styles`` tokens; no colors or radii are
hardcoded here.

Buridan UI docs consulted:
- Button: https://buridan-ui.reflex.run/docs/components/button
- Input:  https://buridan-ui.reflex.run/docs/components/input
- Field:  https://buridan-ui.reflex.run/docs/components/field
- Spinner: https://buridan-ui.reflex.run/docs/components/spinner
- Avatar: https://buridan-ui.reflex.run/docs/components/avatar
"""

from __future__ import annotations

import reflex as rx

from WisPay.styles import Styles, Tokens

_AUTH_PAGE_STYLE: rx.Style = rx.Style(
    {
        "min_height": "100vh",
        "display": "flex",
        "flex_direction": "column",
        "align_items": "center",
        "justify_content": "center",
        "background_color": Tokens.BG,
        "color": Tokens.FG,
        "padding": "var(--ws-space-6)",
        "animation": "wispay-page-in var(--ws-motion-base) var(--ws-ease-standard) both",
    }
)


_AUTH_CARD_STYLE: rx.Style = rx.Style(
    {
        "display": "flex",
        "flex_direction": "column",
        "align_items": "center",
        "gap": "var(--ws-space-5)",
        "width": "min(100%, 440px)",
        "background_color": Tokens.BG,
        "border_radius": "var(--ws-radius-md)",
        "box_shadow": Tokens.ELEV_RING,
        "padding": "var(--ws-space-8)",
        "text_align": "center",
    }
)


_AUTH_BRAND_STYLE: rx.Style = rx.Style(
    {
        "display": "inline-flex",
        "align_items": "center",
        "gap": "10px",
        "text_decoration": "none",
        "color": Tokens.FG,
    }
)


_AUTH_HEADING_STYLE: rx.Style = rx.Style(
    {
        **Styles.display_heading,
        "font_size": "var(--ws-text-3xl)",
        "margin": "0",
    }
)


_AUTH_LEDE_STYLE: rx.Style = rx.Style(
    {
        "max_width": "38ch",
        "color": Tokens.FG_2,
        "font_family": Tokens.FONT_BODY,
        "font_size": "var(--ws-text-base)",
        "line_height": "1.5",
        "margin": "0",
    }
)


_AUTH_ACTIONS_STYLE: rx.Style = rx.Style(
    {
        "display": "flex",
        "flex_direction": "column",
        "align_items": "stretch",
        "gap": "var(--ws-space-3)",
        "width": "100%",
    }
)


_SPINNER_WRAP_STYLE: rx.Style = rx.Style(
    {
        "display": "flex",
        "flex_direction": "column",
        "align_items": "center",
        "gap": "var(--ws-space-4)",
    }
)


def auth_page(*children: rx.Component) -> rx.Component:
    """Render a centered, chrome-free authentication page frame.

    Wraps content in a full-viewport centered flex column so the auth surface
    stands alone without the application sidebar shell. Use for login, signup,
    callback, and logout pages.

    Args:
        *children: Page content components.

    Usage::

        auth_page(login_card())
    """
    return rx.el.div(
        *children,
        style=_AUTH_PAGE_STYLE,
    )


def auth_card(*children: rx.Component) -> rx.Component:
    """Render the centered white surface card for auth content.

    A single elevated card with ring shadow holding the brand mark, heading,
    lede, and action surface. Visual values come from the card token family.

    Args:
        *children: Card content components (brand mark, heading, buttons).

    Usage::

        auth_card(brand_mark(), heading(), actions())
    """
    return rx.el.div(
        *children,
        style=_AUTH_CARD_STYLE,
    )


def auth_brand_mark() -> rx.Component:
    """Render the WisPay brand mark and wordmark linking to home.

    A black-on-white inline-flex link showing ``/brand-mark.svg`` plus the
    WisPay wordmark in display type. Never recolored for status.

    Usage::
        auth_brand_mark()
    """
    return rx.link(
        rx.image(
            src="/brand-mark.svg",
            alt="WisPay mark",
            class_name="wispay-brand-mark",
        ),
        rx.text("WisPay", class_name="wispay-brand-wordmark"),
        href="/",
        aria_label="WisPay home",
        style=_AUTH_BRAND_STYLE,
    )


def auth_heading(text: str) -> rx.Component:
    """Render the light display heading for an auth page.

    Args:
        text: Heading copy (sentence case per DESIGN voice).

    Usage::
        auth_heading("Sign in")
    """
    return rx.heading(text, style=_AUTH_HEADING_STYLE)


def auth_lede(text: str) -> rx.Component:
    """Render the single explanatory sentence under an auth heading.

    Args:
        text: One short explanatory sentence.

    Usage::
        auth_lede("WisPay uses corporate single sign-on.")
    """
    return rx.text(text, style=_AUTH_LEDE_STYLE)


def auth_actions(*children: rx.Component) -> rx.Component:
    """Render the stacked action surface inside an auth card.

    Args:
        *children: Button/link components, full-width stretch.

    Usage::
        auth_actions(sign_in_button(), request_access_link())
    """
    return rx.el.div(
        *children,
        style=_AUTH_ACTIONS_STYLE,
    )


def auth_spinner(label: str) -> rx.Component:
    """Render a centered spinner with a mono caption for transition pages.

    Args:
        label: Mono caption shown beneath the spinner (e.g. "Completing sign-in…").

    Usage::
        auth_spinner("Completing sign-in…")
    """
    return rx.el.div(
        rx.spinner(size="3"),
        rx.text(label, style=Styles.meta),
        style=_SPINNER_WRAP_STYLE,
    )


def auth_banner(message: rx.Var[str] | str) -> rx.Component:
    """Render the danger sign-in banner shown when authentication fails.

    A restrained danger-tinted row per DESIGN banners: short strong lead plus
    the error copy. Hidden entirely while ``message`` is empty.

    Args:
        message: Error text; a state var such as ``AuthState.auth_error``.

    Usage::
        auth_banner(AuthState.auth_error)
    """
    return rx.cond(
        message != "",
        rx.el.div(
            rx.el.p("Sign-in problem", style=_BANNER_LEAD_STYLE),
            rx.el.span(message, style=_BANNER_COPY_STYLE),
            role="alert",
            style=_BANNER_STYLE,
        ),
        rx.fragment(),
    )


_BANNER_STYLE: rx.Style = rx.Style(
    {
        "width": "100%",
        "display": "flex",
        "flex_direction": "column",
        "gap": "var(--ws-space-1)",
        "background_color": "color-mix(in srgb, var(--ws-danger) 8%, transparent)",
        "border": f"1px solid color-mix(in srgb, {Tokens.DANGER} 35%, transparent)",
        "border_radius": "var(--ws-radius-md)",
        "padding": "var(--ws-space-4)",
        "text_align": "left",
    }
)


_BANNER_LEAD_STYLE: rx.Style = rx.Style(
    {
        "margin": "0",
        "font_family": Tokens.FONT_MONO,
        "font_size": "11px",
        "letter_spacing": "0.08em",
        "text_transform": "uppercase",
        "color": Tokens.DANGER,
    }
)


_BANNER_COPY_STYLE: rx.Style = rx.Style(
    {
        "font_family": Tokens.FONT_BODY,
        "font_size": "13px",
        "color": Tokens.FG_2,
    }
)

__all__ = [
    "auth_actions",
    "auth_banner",
    "auth_brand_mark",
    "auth_card",
    "auth_heading",
    "auth_lede",
    "auth_page",
    "auth_spinner",
]
