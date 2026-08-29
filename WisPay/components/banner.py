"""Full-width banner components for WisPay.

Banners communicate a single strong lead plus restrained body copy. Tones map
to the four banner kinds described in ``DESIGN.md``: danger (blocking
over-budget), warning (duplicate / deadline), info (explanatory framing), and
success (recorded-payment confirmation). The component renders nothing while
its ``message`` argument is empty so it can be bound directly to a state var.

Usage::

    from WisPay.components.banner import banner

    banner(
        lead="Recorded payment",
        message=payments_state.last_confirmation,
        tone="success",
    )
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx


class BannerTone:
    """Tone identifiers for the banner component."""

    INFO: ClassVar[str] = "info"
    SUCCESS: ClassVar[str] = "success"
    WARNING: ClassVar[str] = "warning"
    DANGER: ClassVar[str] = "danger"


def banner(
    lead: str,
    message: rx.Var[str] | str,
    *,
    tone: str = BannerTone.INFO,
) -> rx.Component:
    """Render a full-width banner with a short strong lead plus body copy.

    Args:
        lead: Short mono-cased label rendered above the message.
        message: Body copy. When empty, the banner collapses to nothing.
        tone: ``BannerTone`` value; defaults to info.

    Usage::

        banner("Sign-in problem", AuthState.auth_error, tone=BannerTone.DANGER)
    """

    return rx.cond(
        message != "",
        rx.el.div(
            rx.el.p(lead, class_name=f"wispay-banner-lead tone-{tone}"),
            rx.el.span(message, class_name="wispay-banner-copy"),
            role="alert",
            class_name=f"wispay-banner tone-{tone}",
        ),
        rx.fragment(),
    )


def info_banner(lead: str, message: rx.Var[str] | str) -> rx.Component:
    """Convenience wrapper for an info-toned banner.

    Usage::

        info_banner("Sample configuration", "Rules are prototype defaults.")
    """

    return banner(lead, message, tone=BannerTone.INFO)


def warning_banner(lead: str, message: rx.Var[str] | str) -> rx.Component:
    """Convenience wrapper for a warning-toned banner.

    Usage::

        warning_banner("Duplicate warning", "Same vendor + invoice + amount.")
    """

    return banner(lead, message, tone=BannerTone.WARNING)


def danger_banner(lead: str, message: rx.Var[str] | str) -> rx.Component:
    """Convenience wrapper for a danger-toned banner.

    Usage::

        danger_banner("Over budget", "Exception approval is required.")
    """

    return banner(lead, message, tone=BannerTone.DANGER)


def success_banner(lead: str, message: rx.Var[str] | str) -> rx.Component:
    """Convenience wrapper for a success-toned banner.

    Usage::

        success_banner("Recorded", "External reference 998-441 captured.")
    """

    return banner(lead, message, tone=BannerTone.SUCCESS)


__all__ = [
    "BannerTone",
    "banner",
    "danger_banner",
    "info_banner",
    "success_banner",
    "warning_banner",
]
