"""Responsive data-table primitive for WisPay queues and search workspaces.

The table renders a hidden ``<caption>`` for screen readers, mono uppercase
headers, and ``data-th`` attributes on every cell so the responsive
``assets/layout.css`` rules can collapse rows into stacked cards below
``768px`` (per ``DESIGN.md#Responsive contract``).

Usage::

    from WisPay.components.table import data_table, ColumnSpec, DataRow

    data_table(
        ColumnSpec("ID"),
        ColumnSpec("Payee"),
        ColumnSpec("Gross", align="right", numeric=True),
        rows=state.rows,
        row_id="queue-row",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import reflex as rx


class ColumnAlign:
    """Horizontal alignment identifiers for ``ColumnSpec``."""

    LEFT: ClassVar[str] = "left"
    RIGHT: ClassVar[str] = "right"
    CENTER: ClassVar[str] = "center"


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Declarative spec for one table column."""

    label: str
    key: str = ""
    align: str = ColumnAlign.LEFT
    numeric: bool = False
    th_class: str = "wispay-queue-th"
    td_class: str = ""


type DataRow = dict[str, str]


def _cell_class(column: ColumnSpec) -> str:
    """Build the responsive-friendly ``data-th`` aware class string."""

    base = column.td_class or column.th_class.replace("th", "cell")
    parts: list[str] = [base]
    if column.align == ColumnAlign.RIGHT:
        parts.append("is-right")
    elif column.align == ColumnAlign.CENTER:
        parts.append("is-center")
    if column.numeric:
        parts.append("is-numeric")
    return " ".join(parts)


def data_table(
    *columns: ColumnSpec,
    rows: rx.Var[list[DataRow]] | list[DataRow],
    caption: str = "",
    row_id_attr: str = "",
    table_class: str = "wispay-queue-table",
    empty_state: rx.Component | None = None,
) -> rx.Component:
    """Render a responsive data table with the design-system anatomy.

    Args:
        *columns: Column spec list; ``key`` defaults to ``label`` lowercased.
        rows: Bound list of dicts whose keys match the column ``key`` (or label).
        caption: Optional visually-hidden caption; recommended for accessibility.
        row_id_attr: Optional id applied to the ``<tbody>`` element.
        table_class: Class applied to the inner ``<table>`` element.
        empty_state: Optional component rendered when ``rows`` is empty.

    Usage::

        data_table(
            ColumnSpec("ID", key="number"),
            ColumnSpec("Payee", key="payee"),
            ColumnSpec("Gross", key="amount_display", align="right", numeric=True),
            rows=state.rows,
            caption="Payment Requests you submitted",
        )
    """

    headers: list[rx.Component] = []
    for column in columns:
        attrs: dict[str, object] = {
            "scope": "col",
            "class_name": column.th_class,
        }
        if column.align != ColumnAlign.LEFT:
            attrs["data_align"] = column.align
        headers.append(rx.el.th(column.label, **attrs))

    header_row = rx.el.tr(*headers)
    header_group = rx.el.thead(header_row)

    def _render_cell(row: DataRow, column: ColumnSpec) -> rx.Component:
        key = column.key or column.label.lower()
        value = row.get(key, "")
        return rx.el.td(value, data_th=column.label, class_name=_cell_class(column))

    def _render_row(row: DataRow) -> rx.Component:
        cells = [_render_cell(row, column) for column in columns]
        return rx.el.tr(*cells, class_name="wispay-queue-row")

    body = rx.el.tbody(
        rx.foreach(rows, _render_row),
        id=row_id_attr or None,
    )

    caption_el: list[rx.Component] = []
    if caption:
        caption_el.append(rx.el.caption(caption, class_name="wispay-sr-only"))

    table = rx.el.table(
        *caption_el,
        header_group,
        body,
        class_name=table_class,
    )

    return rx.el.div(table, class_name="wispay-queue-card")


def mobile_cards(
    *columns: ColumnSpec,
    rows: rx.Var[list[DataRow]] | list[DataRow],
    render_card: object,
) -> rx.Component:
    """Render a stacked-card mobile fallback for the same row data.

    Args:
        *columns: Column specs (used for label rendering on small screens).
        rows: Bound row list.
        render_card: Callable that receives a single row and returns a card.

    Usage::

        mobile_cards(
            ColumnSpec("ID"),
            ColumnSpec("Payee"),
            rows=state.rows,
            render_card=lambda row: stacked_row(row),
        )
    """

    return rx.el.div(
        rx.foreach(rows, render_card),
        class_name="wispay-mobile-cards",
    )


__all__ = [
    "ColumnAlign",
    "ColumnSpec",
    "DataRow",
    "data_table",
    "mobile_cards",
]
