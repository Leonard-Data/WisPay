"""Waveform amount strip — the single expressive flourish on request detail.

A deterministic, finance-native sequence of vertical bars that visually
encodes the amount context. It is decorative: every render is paired with
the plain gross amount and the text "Records external payment completion"
so the data stays accessible (per ``DESIGN.md#Waveform amount strip``).

Usage::

    from WisPay.components.waveform_amount_strip import waveform_amount_strip

    waveform_amount_strip(
        label="Gross request in USD",
        height=80,
    )
"""

from __future__ import annotations

from dataclasses import dataclass

import reflex as rx

_BAR_COUNT: int = 32


@dataclass(frozen=True, slots=True)
class WaveBar:
    """One segment in the waveform amount strip."""

    index: int
    height: int
    is_active: bool


def _default_heights(active_until: int = 18) -> tuple[WaveBar, ...]:
    """Build the default deterministic 32-bar waveform."""

    return tuple(
        WaveBar(
            index=i,
            height=18 + 2 * i + (i % 3) * 4,
            is_active=i < active_until,
        )
        for i in range(_BAR_COUNT)
    )


def waveform_amount_strip(
    *,
    label: str | rx.Var[str] = "Gross request",
    active_until: int = 18,
    height_px: int = 56,
) -> rx.Component:
    """Render the segmented waveform amount strip.

    Args:
        label: Accessible label rendered as the role=img name.
        active_until: Index up to which bars are filled (others are dim).
        height_px: Container height in pixels.

    Usage::

        waveform_amount_strip(label="Gross request in USD")
    """

    bars = _default_heights(active_until=max(0, min(_BAR_COUNT, active_until)))
    children = [
        rx.el.span(
            style={"height": f"{bar.height}px"},
            class_name=(
                "wispay-detail-wave-bar is-active" if bar.is_active else "wispay-detail-wave-bar"
            ),
            key=f"wave-bar-{bar.index}",
        )
        for bar in bars
    ]
    return rx.el.div(
        *children,
        role="img",
        aria_label=label,
        style={"height": f"{height_px}px"},
        class_name="wispay-detail-wave",
    )


__all__ = [
    "WaveBar",
    "waveform_amount_strip",
]
