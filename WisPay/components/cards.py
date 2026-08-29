"""Card surface components shared across WisPay pages.

Wraps the three design-system card variants (default white, inset, warm) as
small composition primitives so pages stay declarative. Visual values come
from ``WisPay.styles`` tokens; the matching CSS lives in
``assets/layout.css`` under ``.wispay-card`` and its variants.

Usage::

    from WisPay.components.cards import card, card_inset, card_warm

    card(
        rx.text("Header"),
        rx.text("Body copy"),
    )
"""

from __future__ import annotations

from typing import ClassVar

import reflex as rx

_CARD_BASE_CLASSES: str = "wispay-card"


class CardTone:
    """Tone identifiers for ``card``-family composition."""

    DEFAULT: ClassVar[str] = "default"
    INSET: ClassVar[str] = "inset"
    WARM: ClassVar[str] = "warm"


def _tone_class(tone: str) -> str:
    """Return the CSS modifier for the requested card tone."""

    if tone == CardTone.INSET:
        return "wispay-card-inset"
    if tone == CardTone.WARM:
        return "wispay-card-warm"
    return _CARD_BASE_CLASSES


def card(*children: rx.Component, tone: str = CardTone.DEFAULT) -> rx.Component:
    """Render a design-system card with the requested tone.

    Args:
        *children: Content to render inside the card.
        tone: One of ``CardTone.DEFAULT`` / ``CardTone.INSET`` / ``CardTone.WARM``.

    Usage::

        card(rx.text("Body"), tone=CardTone.WARM)
    """

    return rx.el.section(
        *children,
        class_name=_tone_class(tone),
    )


def card_inset(*children: rx.Component) -> rx.Component:
    """Convenience wrapper for the inset (surface-toned) card.

    Usage::

        card_inset(rx.text("Filter form"))
    """

    return card(*children, tone=CardTone.INSET)


def card_warm(*children: rx.Component) -> rx.Component:
    """Convenience wrapper for the warm-context card.

    Usage::

        card_warm(amount_panel())
    """

    return card(*children, tone=CardTone.WARM)


def card_with_heading(
    *,
    heading_id: str = "",
    kicker: str | rx.Var[str] | None = None,
    title: str | rx.Var[str] | None = None,
    body: rx.Component | None = None,
    tone: str = CardTone.DEFAULT,
) -> rx.Component:
    """Render a card with the standard kicker/title heading block.

    Args:
        heading_id: Optional DOM id for the heading region.
        kicker: Mono uppercase kicker string (e.g. ``"Workspace"``).
        title: Display title string.
        body: Optional body component placed under the heading.
        tone: Card tone identifier.

    Usage::

        card_with_heading(
            kicker="Workspace",
            title="Awaiting my action",
            body=queue_table(),
        )
    """

    heading_children: list[rx.Component] = []
    if kicker is not None:
        heading_children.append(rx.text(kicker, class_name="wispay-card-kicker"))
    if title is not None:
        heading_children.append(rx.text(title, class_name="wispay-card-title"))
    heading_block = rx.box(
        *heading_children,
        class_name="wispay-card-heading",
    )
    children: list[rx.Component] = [heading_block]
    if body is not None:
        children.append(body)
    kwargs: dict[str, object] = {"class_name": _tone_class(tone)}
    if heading_id:
        kwargs["id"] = heading_id
    return rx.el.section(*children, **kwargs)


__all__ = [
    "CardTone",
    "card",
    "card_inset",
    "card_warm",
    "card_with_heading",
]
