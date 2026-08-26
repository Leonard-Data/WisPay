"""Labelled-form component family shared across WisPay screens.

Covers the recurring field pattern: a caption row (label plus optional
Required/Optional tag), a bound control, and an optional inline error line,
plus the select-option renderer. Components here are page-agnostic: value
and change-handler wiring are caller arguments, never hard-coded state, so
the same primitive serves the create-request wizard and any future form.

Usage::

    from WisPay.components.form_fields import form_field, form_select, form_text_input

    form_field(
        "Cost center",
        form_select(
            DraftState.cost_center,
            DraftState.set_cost_center,
            options=COST_CENTERS,
            placeholder=True,
        ),
        tag="Required",
        error=DraftState.errors["cost_center"],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx

if TYPE_CHECKING:
    from collections.abc import Sequence


def _options(options: Sequence[tuple[str, str]] | Sequence[str]) -> list[rx.Component]:
    """Render ``<option>`` elements from ``(code, name)`` pairs or bare strings."""

    normalized: list[tuple[str, str]] = [
        item if isinstance(item, tuple) else (item, item) for item in options
    ]
    return [
        rx.el.option(name, value=code, key=f"{code}-{index}")
        for index, (code, name) in enumerate(normalized)
    ]


def form_text_input(
    value: rx.Var[str] | str,
    on_change: Any,
    *,
    input_id: str = "",
    placeholder: str = "",
    input_type: str = "text",
    invalid: rx.Var[bool] | bool | None = None,
) -> rx.Component:
    """Render a single-line input bound to ``value``/``on_change``.

    Args:
        value: State var or literal holding the current text.
        on_change: Event handler receiving the edited string.
        input_id: DOM id (e.g. ``fld-title``) for tests and labels; omitted when empty.
        placeholder: Placeholder copy shown while empty.
        input_type: HTML input type (``text``, ``date``, ``number``, ...).
        invalid: When given, toggles ``aria-invalid`` between true/false.

    Usage::
        form_text_input(DraftState.title, DraftState.set_title, input_id="fld-title")
    """

    kwargs: dict[str, Any] = {
        "placeholder": placeholder,
        "type": input_type,
        "value": value,
        "on_change": on_change,
        "class_name": "wispay-new-input",
    }
    if input_id:
        kwargs["id"] = input_id
    if invalid is not None:
        kwargs["aria_invalid"] = rx.cond(invalid, "true", "false")
    return rx.el.input(**kwargs)


def form_select(
    value: rx.Var[str] | str,
    on_change: Any,
    *,
    options: Sequence[tuple[str, str]] | Sequence[str],
    input_id: str = "",
    placeholder: bool = False,
) -> rx.Component:
    """Render a select bound to ``value``/``on_change`` from raw option data.

    Args:
        value: State var or literal holding the selected code.
        on_change: Event handler receiving the selected code.
        options: ``(code, name)`` pairs or bare strings.
        input_id: DOM id for tests and labels; omitted when empty.
        placeholder: Prepend a disabled "Select…" row for empty-default fields.

    Usage::
        form_select(DraftState.currency, DraftState.set_currency, options=CURRENCIES)
    """

    children = (
        [rx.el.option("Select…", value="", disabled=True, key=f"ph-{input_id}"), *_options(options)]
        if placeholder
        else _options(options)
    )
    kwargs: dict[str, Any] = {
        "value": value,
        "on_change": on_change,
        "class_name": "wispay-new-input wispay-new-select",
    }
    if input_id:
        kwargs["id"] = input_id
    return rx.el.select(*children, **kwargs)


def form_field(
    label: str,
    control: rx.Component,
    *,
    tag: str = "",
    error: rx.Var[str] | str = "",
    error_id: str = "",
) -> rx.Component:
    """Render one labelled form field with an optional tag and error line.

    Args:
        label: Field caption text.
        control: The input/select/textarea nested inside the label.
        tag: Optional badge after the label (e.g. ``"Required"``); omitted when empty.
        error: Error message var or string; the line renders only while non-empty.
        error_id: DOM id for the error line (aria target); omitted when empty.

    Usage::
        form_field("Title", form_text_input(...), tag="Required", error=DraftState.title_error)
    """

    caption: rx.Component = rx.el.span(label, class_name="wispay-new-field-label")
    if tag:
        caption = rx.el.span(
            label,
            rx.el.span(tag, class_name="wispay-new-field-tag"),
            class_name="wispay-new-field-label",
        )

    error_kwargs: dict[str, Any] = {"class_name": "wispay-new-field-error"}
    if error_id:
        error_kwargs["id"] = error_id

    return rx.el.label(
        caption,
        control,
        rx.cond(error != "", rx.el.span(error, **error_kwargs), rx.fragment()),
        class_name="wispay-new-field",
    )
