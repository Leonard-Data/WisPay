"""RequestCreateState-bound field builders for the create-request wizard.

Thin adapters between the shared primitives in
``WisPay.components.form_fields`` and the wizard's draft state: ids, error
wiring, and ``set_field`` binding stay here so step modules only describe
layout. Only sibling wizard modules may import these helpers.

Usage::

    from WisPay.pages.request_new.controls import field, select, text_input

    field("Cost center", "cost_center", select("cost_center", COST_CENTERS))
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import reflex as rx

if TYPE_CHECKING:
    from collections.abc import Sequence

from states.request_create import RequestCreateState
from WisPay.components.form_fields import form_field, form_select, form_text_input


def field(label: str, name: str, control: rx.Component, *, required: bool = True) -> rx.Component:
    """Render one labelled wizard field wired to the draft-state error map.

    Args:
        label: Field caption text.
        name: Draft-state field key; drives the error lookup and DOM id prefix.
        control: The input/select/textarea nested inside the label.
        required: Chooses the Required/Optional badge.

    Usage::
        field("Request title", "title", text_input("title"))
    """

    return form_field(
        label,
        control,
        tag="Required" if required else "Optional",
        error=rx.cond(
            RequestCreateState.error_fields.contains(name),
            RequestCreateState.field_errors[name],
            "",
        ),
        error_id=f"error-{name}",
    )


def text_input(name: str, placeholder: str = "", *, input_type: str = "text") -> rx.Component:
    """Render the named draft-field text input bound to ``set_field``.

    Args:
        name: Draft-state field key; also becomes the ``fld-<name>`` DOM id.
        placeholder: Placeholder copy shown while empty.
        input_type: HTML input type (``text``, ``date``, ``number``, ...).

    Usage::
        text_input("invoice_date", input_type="date")
    """

    return form_text_input(
        getattr(RequestCreateState, name),
        RequestCreateState.set_field(name),  # type: ignore[operator]
        input_id=f"fld-{name}",
        placeholder=placeholder,
        input_type=input_type,
        invalid=RequestCreateState.error_fields.contains(name),
    )


def select(
    name: str,
    options: Sequence[tuple[str, str]] | Sequence[str],
    *,
    placeholder: bool = False,
) -> rx.Component:
    """Render the named draft-field select bound to ``set_field``.

    Args:
        name: Draft-state field key; also becomes the ``fld-<name>`` DOM id.
        options: ``(code, name)`` pairs or bare strings to offer.
        placeholder: Prepend a disabled "Select…" row for empty-default fields.

    Usage::
        select("currency", CURRENCY_OPTIONS)
    """

    return form_select(
        getattr(RequestCreateState, name),
        RequestCreateState.set_field(name),  # type: ignore[operator]
        options=options,
        input_id=f"fld-{name}",
        placeholder=placeholder,
    )


def subtype_heading() -> rx.Component:
    """Render the Details heading copy for the currently selected subtype.

    Usage::
        rx.el.h2(subtype_heading(), class_name="wispay-new-h3")
    """

    return rx.cond(
        RequestCreateState.family == "vendor",
        "Vendor payment details",
        rx.cond(
            RequestCreateState.subtype == "reimbursement",
            "Reimbursement details",
            rx.cond(
                RequestCreateState.subtype == "advance",
                "Cash advance details",
                rx.cond(
                    RequestCreateState.subtype == "settlement",
                    "Advance settlement details",
                    "Internal expenditure details",
                ),
            ),
        ),
    )
