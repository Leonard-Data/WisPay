"""Tab strip components for WisPay.

A single horizontal tab row with a bottom rule, an active 2px bottom line in
``--fg``, hover on ``--surface``, and a mono count badge per
``DESIGN.md#Tabs``. On small screens the row scrolls horizontally instead of
clipping.

Usage::

    from WisPay.components.tabs import tab_strip, TabSpec

    tab_strip(
        TabSpec("Summary", count=12),
        TabSpec("Audit", count=4),
        selected=request_detail_ui_state.selected_tab,
        on_select=request_detail_ui_state.select_tab,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import reflex as rx


class TabVariant:
    """Tab visual variant identifiers."""

    DEFAULT: ClassVar[str] = "default"
    COMPACT: ClassVar[str] = "compact"


@dataclass(frozen=True, slots=True)
class TabSpec:
    """Declarative spec for one tab in a strip."""

    label: str
    count: int | None = None
    key: str = ""


def _active_condition(
    selected: rx.Var[str] | str,
    label: str,
) -> rx.Var[bool] | bool:
    """Build a boolean expression marking the active tab."""

    result: rx.Var[bool] | bool = selected == label
    return result


def tab_strip(
    *tabs: TabSpec,
    selected: rx.Var[str] | str,
    on_select: object,
    aria_label: str = "Tabs",
    variant: str = TabVariant.DEFAULT,
) -> rx.Component:
    """Render a horizontal tab strip with optional count badges.

    Args:
        *tabs: The ordered tabs to render.
        selected: Bound state var (or literal) holding the active tab label.
        on_select: Event handler receiving the chosen tab label.
        aria_label: Accessible group label.
        variant: ``TabVariant`` value; defaults to default.

    Usage::

        tab_strip(
            TabSpec("Summary"),
            TabSpec("Documents", count=3),
            selected=request_detail_ui_state.selected_tab,
            on_select=request_detail_ui_state.select_tab,
        )
    """

    items: list[rx.Component] = []
    for index, tab in enumerate(tabs):
        label = tab.label
        is_active_var = _active_condition(selected, label)
        items.append(
            rx.el.button(
                rx.el.span(label, class_name="wispay-tabs-label"),
                rx.cond(
                    tab.count is not None,
                    rx.el.span(
                        f"{tab.count}",
                        class_name="wispay-tabs-count",
                    ),
                    rx.fragment(),
                ),
                type="button",
                role="tab",
                aria_selected=rx.cond(is_active_var, "true", "false"),
                on_click=lambda lbl=label: on_select(lbl),  # type: ignore[operator]
                class_name=rx.cond(
                    is_active_var,
                    f"wispay-tabs-item is-active is-{variant}",
                    f"wispay-tabs-item is-{variant}",
                ),
                key=tab.key or f"tab-{index}",
            )
        )

    return rx.el.div(
        *items,
        role="tablist",
        aria_label=aria_label,
        class_name=f"wispay-tabs is-{variant}",
    )


__all__ = [
    "TabSpec",
    "TabVariant",
    "tab_strip",
]
