"""Status pill components for WisPay.

Pill is a dot-plus-label surface that pairs with ``.wispay-pill`` and the
tone modifiers in ``assets/layout.css`` (``tone-neutral``, ``tone-info``,
``tone-ok``, ``tone-warn``, ``tone-danger``, ``tone-accent``). The flag chip
mirrors the secondary derived badges (Overdue, Duplicate, Exception, Window,
Settlement Breach).

Usage::

    from WisPay.components.status_pill import status_pill, flag_chip

    status_pill("Approved", tone="ok")
    flag_chip("Overdue", tone="warn")
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx


class PillTone:
    """Tone identifiers for status pills and flag chips."""

    NEUTRAL: ClassVar[str] = "neutral"
    INFO: ClassVar[str] = "info"
    OK: ClassVar[str] = "ok"
    WARN: ClassVar[str] = "warn"
    DANGER: ClassVar[str] = "danger"
    ACCENT: ClassVar[str] = "accent"


def status_pill(label: rx.Var[str] | str, *, tone: str = PillTone.NEUTRAL) -> rx.Component:
    """Render a dot-plus-label status pill.

    Args:
        label: Pill text (lifecycle state, decision, payment status).
        tone: Pill tone (``PillTone``); defaults to neutral.

    Usage::

        status_pill("Approved", tone=PillTone.OK)
    """

    return rx.el.span(
        rx.el.span(class_name="wispay-pill-dot"),
        label,
        class_name=f"wispay-pill tone-{tone}",
    )


def flag_chip(
    label: rx.Var[str] | str,
    *,
    tone: str = PillTone.WARN,
) -> rx.Component:
    """Render a compact derived-flag chip (Overdue, Duplicate, …).

    Args:
        label: Short uppercase label.
        tone: Chip tone; defaults to warning.

    Usage::

        flag_chip("Overdue")
    """

    return rx.el.span(label, class_name=f"wispay-flagchip {tone}")


__all__ = [
    "PillTone",
    "flag_chip",
    "status_pill",
]
