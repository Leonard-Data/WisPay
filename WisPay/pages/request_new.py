"""New Payment Request wizard screen (``/requests/new``).

Visual contract: ``docs/product/DESIGN.md`` plus the ``new-request.html``
source example (four steps: Type → Details → Documents → Review). All
behavior routes through ``states.request_create.RequestCreateState`` and the
creation services — no business logic lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx

if TYPE_CHECKING:
    from collections.abc import Sequence


from states.request_create import RequestCreateState
from WisPay.layout.shell import shell
from WisPay.services.reference_data import (
    COST_CENTERS,
    EXPENSE_CATEGORIES,
    LEGAL_ENTITIES,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    POLICY_CATEGORIES,
)

_STEPS = ("Type", "Details", "Documents", "Review")
_EMPLOYEE_TYPES: tuple[tuple[str, str], ...] = (
    ("reimbursement", "Reimbursement"),
    ("advance", "Cash advance"),
    ("settlement", "Advance settlement"),
    ("internal", "Internal expenditure"),
)
_TYPE_COPY: dict[str, str] = {
    "standard": "Pay an invoice from a supplier or service provider.",
    "reimbursement": "Repay an employee for approved out-of-pocket spend.",
    "advance": "Release funds before an approved activity begins.",
    "settlement": "Reconcile actual expenses against an open advance.",
    "internal": "Record approved spend that does not use a vendor invoice.",
}
_CURRENCY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("VND", "VND ₫"),
    ("USD", "USD $"),
    ("EUR", "EUR €"),
)


def _options(options: Sequence[tuple[str, str]] | Sequence[str]) -> list[rx.Component]:
    """Render select options from code/name pairs or bare strings."""

    normalized: list[tuple[str, str]] = [
        item if isinstance(item, tuple) else (item, item) for item in options
    ]
    return [
        rx.el.option(name, value=code, key=f"{code}-{index}")
        for index, (code, name) in enumerate(normalized)
    ]


def _field(
    label: str,
    name: str,
    control: rx.Component,
    *,
    required: bool = True,
) -> rx.Component:
    """One labelled wizard field; the control nests inside the label."""

    return rx.el.label(
        rx.el.span(
            label,
            rx.el.span("Required" if required else "Optional", class_name="wispay-new-field-tag"),
            class_name="wispay-new-field-label",
        ),
        control,
        rx.cond(
            RequestCreateState.error_fields.contains(name),
            rx.el.span(
                RequestCreateState.field_errors[name],
                id=f"error-{name}",
                class_name="wispay-new-field-error",
            ),
            rx.fragment(),
        ),
        class_name="wispay-new-field",
    )


def _text_input(name: str, placeholder: str = "", *, input_type: str = "text") -> rx.Component:
    return rx.el.input(
        id=f"fld-{name}",
        placeholder=placeholder,
        type=input_type,
        value=getattr(RequestCreateState, name),
        on_change=RequestCreateState.set_field(name),  # type: ignore[operator]
        aria_invalid=rx.cond(RequestCreateState.error_fields.contains(name), "true", "false"),
        class_name="wispay-new-input",
    )


def _select(name: str, options: list[rx.Component], *, placeholder: bool = False) -> rx.Component:
    """Render a select; empty-default fields get an explicit placeholder."""

    children = (
        [rx.el.option("Select…", value="", disabled=True, key=f"ph-{name}"), *options]
        if placeholder
        else options
    )
    return rx.el.select(
        *children,
        id=f"fld-{name}",
        value=getattr(RequestCreateState, name),
        on_change=RequestCreateState.set_field(name),  # type: ignore[operator]
        class_name="wispay-new-input wispay-new-select",
    )


def _step_bar() -> rx.Component:
    buttons: list[rx.Component] = []
    for index, label in enumerate(_STEPS, start=1):
        buttons.append(
            rx.el.button(
                rx.el.span(str(index), class_name="wispay-new-step-num"),
                rx.el.span(label),
                type="button",
                class_name=rx.cond(
                    RequestCreateState.step == index,
                    "wispay-new-step is-active",
                    rx.cond(
                        RequestCreateState.step > index,
                        "wispay-new-step is-done",
                        "wispay-new-step is-future",
                    ),
                ),
                aria_current=rx.cond(RequestCreateState.step == index, "step", ""),
                on_click=lambda idx=index: RequestCreateState.go_to_step(idx),  # type: ignore[operator]
                key=f"wispay-new-step-{index}",
            )
        )
    return rx.el.div(
        *buttons, role="group", aria_label="Request progress", class_name="wispay-new-steps"
    )


def _type_card(subtype_key: str, label: str, family_key: str) -> rx.Component:
    selected = (RequestCreateState.family == family_key) & (
        RequestCreateState.subtype == subtype_key
    )
    return rx.el.button(
        rx.el.span(label, class_name="wispay-new-type-title"),
        rx.el.span(_TYPE_COPY[subtype_key], class_name="wispay-new-type-copy"),
        rx.el.span(rx.cond(selected, "Selected", "Choose"), class_name="wispay-new-type-state"),
        type="button",
        class_name=rx.cond(selected, "wispay-new-type-card is-selected", "wispay-new-type-card"),
        aria_pressed=rx.cond(selected, "true", "false"),
        on_click=RequestCreateState.select_type(family_key, subtype_key),  # type: ignore[operator]
        key=f"type-{subtype_key}",
    )


def _step_type() -> rx.Component:
    return rx.el.section(
        rx.el.p("Step 1 · Request type", class_name="wispay-new-eyebrow"),
        rx.el.h2("What are you requesting?", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p(
            "Choose the route that matches the payment. The next step adapts to your selection.",
            class_name="wispay-new-muted",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.strong("Supplier payments"),
                    rx.el.span("1 option", class_name="wispay-new-meta"),
                    class_name="wispay-new-group-label",
                ),
                rx.el.div(
                    _type_card("standard", "Vendor payment", "vendor"),
                    class_name="wispay-new-type-grid is-single",
                ),
                class_name="wispay-new-group",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.strong("Employee payments"),
                    rx.el.span("4 options", class_name="wispay-new-meta"),
                    class_name="wispay-new-group-label",
                ),
                rx.el.div(
                    *[_type_card(key, label, "employee") for key, label in _EMPLOYEE_TYPES],
                    class_name="wispay-new-type-grid",
                ),
                class_name="wispay-new-group",
            ),
        ),
        class_name="wispay-new-panel",
        id="wizard-step-title",
    )


def _subtype_heading() -> rx.Component:
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


def _vendor_identity_fields() -> rx.Component:
    return rx.fragment(
        _field("Vendor", "vendor_name", _text_input("vendor_name", "Supplier legal name")),
        _field("Invoice number", "invoice_number", _text_input("invoice_number", "INV-XXXX")),
        _field("Invoice date", "invoice_date", _text_input("invoice_date", input_type="date")),
        _field("Payment due date", "due_date", _text_input("due_date", input_type="date")),
        _field(
            "Payment terms",
            "payment_terms_code",
            _select(
                "payment_terms_code",
                _options([(o.code, o.name) for o in PAYMENT_TERMS]),
                placeholder=True,
            ),
        ),
        _field(
            "Proposed payment method",
            "payment_method_code",
            _select(
                "payment_method_code",
                _options([(o.code, o.name) for o in PAYMENT_METHODS]),
                placeholder=True,
            ),
        ),
    )


def _employee_identity_fields() -> rx.Component:
    return rx.cond(
        RequestCreateState.subtype == "reimbursement",
        rx.fragment(
            _field("Merchant / payee", "merchant", _text_input("merchant", "Merchant name")),
            _field("Expense date", "expense_date", _text_input("expense_date", input_type="date")),
            _field(
                "Policy category",
                "policy_category",
                _select("policy_category", _options(POLICY_CATEGORIES), placeholder=True),
            ),
        ),
        rx.cond(
            RequestCreateState.subtype == "advance",
            rx.fragment(
                _field(
                    "Activity start",
                    "activity_start",
                    _text_input("activity_start", input_type="date"),
                ),
                _field(
                    "Activity end", "activity_end", _text_input("activity_end", input_type="date")
                ),
            ),
            rx.cond(
                RequestCreateState.subtype == "settlement",
                rx.fragment(
                    rx.cond(
                        RequestCreateState.settleable_advances.length() > 0,
                        rx.el.select(
                            rx.el.option("Select open advance…", value="", disabled=True),
                            rx.foreach(
                                RequestCreateState.settleable_advances,
                                lambda advance: rx.el.option(
                                    advance["number"] + " · " + advance["title"],
                                    value=advance["request_id"],
                                    key=advance["request_id"],
                                ),
                            ),
                            id="fld-linked_advance_id",
                            value=RequestCreateState.linked_advance_id,
                            on_change=RequestCreateState.set_field("linked_advance_id"),  # type: ignore[operator]
                            class_name="wispay-new-input wispay-new-select",
                        ),
                        rx.el.div(
                            rx.el.h4("No open advances", class_name="wispay-new-h4"),
                            rx.el.p(
                                "A submitted cash advance must exist in this session "
                                "before it can be settled.",
                                class_name="wispay-new-muted",
                            ),
                            class_name="wispay-new-callout",
                        ),
                    ),
                ),
                rx.fragment(
                    _field(
                        "Policy category",
                        "policy_category",
                        _select("policy_category", _options(POLICY_CATEGORIES), placeholder=True),
                    ),
                ),
            ),
        ),
    )


def _step_details() -> rx.Component:
    amount_label = rx.cond(RequestCreateState.family == "vendor", "Net amount", "Amount")
    return rx.el.section(
        rx.el.p("Step 2 · Details", class_name="wispay-new-eyebrow"),
        rx.el.h2(_subtype_heading(), class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p("Required fields are checked before you continue.", class_name="wispay-new-muted"),
        rx.el.div(
            rx.el.div(
                rx.el.h3("Request"),
                rx.el.p(
                    "Name the request and identify who is paid.", class_name="wispay-new-muted"
                ),
                class_name="wispay-new-section-head",
            ),
            rx.el.div(
                _field("Request title", "title", _text_input("title", "Brief descriptive title")),
                rx.cond(
                    RequestCreateState.family == "vendor",
                    _vendor_identity_fields(),
                    _employee_identity_fields(),
                ),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.h3("Accounting & amount"),
                rx.el.p("Assign the spend and confirm the amount.", class_name="wispay-new-muted"),
                class_name="wispay-new-section-head",
            ),
            rx.el.div(
                _field(
                    "Legal entity",
                    "legal_entity",
                    _select(
                        "legal_entity",
                        _options([(o.code, o.name) for o in LEGAL_ENTITIES]),
                        placeholder=True,
                    ),
                ),
                _field(
                    "Cost center",
                    "cost_center",
                    _select(
                        "cost_center",
                        _options([(o.code, o.name) for o in COST_CENTERS]),
                        placeholder=True,
                    ),
                ),
                _field("Project", "project", _text_input("project", "PRJ-XXX"), required=False),
                _field(
                    "Expense category",
                    "expense_category",
                    _select(
                        "expense_category",
                        _options([(o.code, o.name) for o in EXPENSE_CATEGORIES]),
                        placeholder=True,
                    ),
                ),
                _field(
                    "Classification",
                    "classification",
                    _select("classification", _options(("OPEX", "CAPEX"))),
                ),
                _field("Budget period", "budget_period", _text_input("budget_period", "YYYY-MM")),
                _field("Currency", "currency", _select("currency", _options(_CURRENCY_OPTIONS))),
                _field(amount_label, "net_text", _text_input("net_text", "0", input_type="number")),
                rx.cond(
                    RequestCreateState.family == "vendor",
                    _field(
                        "VAT amount", "vat_text", _text_input("vat_text", "0", input_type="number")
                    ),
                    rx.fragment(),
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.strong("Gross amount"),
                        rx.el.small(
                            rx.cond(
                                RequestCreateState.family == "vendor",
                                "Net plus VAT",
                                "Requested amount",
                            )
                        ),
                        class_name="wispay-new-gross-label",
                    ),
                    rx.el.span(
                        rx.cond(
                            RequestCreateState.gross_preview != "",
                            RequestCreateState.gross_preview,
                            "—",
                        ),
                        class_name="wsp-num wispay-new-gross-value",
                    ),
                    class_name="wispay-new-gross-card",
                    aria_live="polite",
                ),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.h3("Business purpose"),
                rx.el.p("Give reviewers enough context to decide.", class_name="wispay-new-muted"),
                class_name="wispay-new-section-head",
            ),
            rx.el.div(
                _field(
                    "Purpose",
                    "purpose",
                    rx.el.textarea(
                        id="fld-purpose",
                        placeholder="Why is this expense needed?",
                        value=RequestCreateState.purpose,
                        on_change=RequestCreateState.set_field("purpose"),  # type: ignore[operator]
                        class_name="wispay-new-input wispay-new-textarea",
                    ),
                ),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        class_name="wispay-new-panel",
    )


def _doc_row(key: str, label: str) -> rx.Component:
    """One checklist row for a known slot; visibility tracks the matrix."""

    listed = RequestCreateState.doc_keys.contains(key)
    met = RequestCreateState.uploaded_keys.contains(key)
    return rx.cond(
        listed,
        rx.el.div(
            rx.el.span(class_name=rx.cond(met, "wispay-new-dot is-met", "wispay-new-dot")),
            rx.el.div(
                rx.el.span(label, class_name="wispay-new-doc-title"),
                rx.el.span(
                    rx.cond(
                        met,
                        "Attached in this session",
                        rx.cond(
                            RequestCreateState.required_doc_keys.contains(key),
                            "Required before submission",
                            "Optional support",
                        ),
                    ),
                    class_name="wispay-new-doc-meta",
                ),
            ),
            rx.el.div(
                rx.cond(
                    met,
                    rx.el.button(
                        "Remove",
                        type="button",
                        on_click=RequestCreateState.remove_upload(key),  # type: ignore[operator]
                    ),
                    rx.el.div(
                        rx.upload(
                            rx.el.span("Choose file", class_name="wispay-new-upload-label"),
                            id=f"upload-{key}",
                            multiple=False,
                            accept={
                                "application/pdf": [".pdf"],
                                "image/png": [".png"],
                                "image/jpeg": [".jpg", ".jpeg"],
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
                                    ".xlsx"
                                ],
                            },
                            max_files=1,
                            class_name="wispay-new-upload-zone",
                        ),
                        rx.el.button(
                            "Attach",
                            type="button",
                            class_name="wispay-button wispay-button-primary wispay-new-attach",
                            on_click=RequestCreateState.handle_upload(
                                rx.upload_files(upload_id=f"upload-{key}")  # type: ignore[operator]
                            ),
                        ),
                        class_name="wispay-new-upload-group",
                    ),
                ),
                class_name="wispay-new-doc-actions",
            ),
            class_name=rx.cond(met, "wispay-new-doc-row is-met", "wispay-new-doc-row"),
        ),
        rx.fragment(),
    )


_DOC_SLOTS: tuple[tuple[str, str], ...] = (
    ("invoice", "Invoice"),
    ("purchase_order", "Purchase order"),
    ("contract", "Contract"),
    ("goods_receipt", "Goods receipt"),
    ("service_acceptance", "Service acceptance"),
    ("receipt", "Receipt"),
    ("expense_statement", "Expense statement"),
    ("activity_evidence", "Activity evidence"),
    ("policy_approval_evidence", "Policy approval evidence"),
)


def _step_documents() -> rx.Component:
    return rx.el.section(
        rx.el.p("Step 3 · Documents", class_name="wispay-new-eyebrow"),
        rx.el.h2("Supporting documents", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p(
            "Attach the evidence reviewers need. Files stay in this session until "
            "durable storage lands.",
            class_name="wispay-new-muted",
        ),
        rx.el.div(
            *[_doc_row(key, label) for key, label in _DOC_SLOTS],
            class_name="wispay-new-doc-checklist wispay-new-card",
        ),
        rx.el.p(
            "Accepted: PDF, PNG, JPG, or XLSX up to 10 MB per file.",
            class_name="wispay-new-callout wsp-note",
        ),
        class_name="wispay-new-panel",
    )


def _summary_row(label: str, value: str | rx.Var[Any] | rx.Component) -> rx.Component:
    return rx.el.div(
        rx.el.dt(label),
        rx.el.dd(value, class_name="wispay-new-num"),
        class_name="wispay-new-summary-row",
    )


def _step_review() -> rx.Component:
    return rx.el.section(
        rx.el.p("Step 4 · Review", class_name="wispay-new-eyebrow"),
        rx.el.h2("Review before submitting", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p("Confirm the request and its evidence.", class_name="wispay-new-muted"),
        rx.cond(
            RequestCreateState.issue_count > 0,
            rx.el.div(
                rx.el.div(
                    rx.el.span("!", class_name="wispay-new-validation-mark"),
                    rx.el.span("Items must be fixed before submission"),
                    class_name="wispay-new-validation-title",
                ),
                rx.el.ul(
                    rx.foreach(
                        RequestCreateState.blocking,
                        lambda item: rx.el.li(item, key=item),
                    ),
                    rx.foreach(
                        RequestCreateState.field_issue_rows,
                        lambda row: rx.el.li(row["message"], key=row["field"]),
                    ),
                    class_name="wispay-new-error-list",
                ),
                rx.el.div(
                    rx.el.button(
                        "Edit details",
                        type="button",
                        class_name="wispay-button wispay-new-button-secondary",
                        on_click=RequestCreateState.go_to_step(2),  # type: ignore[operator]
                    ),
                    rx.el.button(
                        "Add documents",
                        type="button",
                        class_name="wispay-button wispay-new-button-ghost",
                        on_click=RequestCreateState.go_to_step(3),  # type: ignore[operator]
                    ),
                    class_name="wispay-new-inline-actions",
                ),
                role="alert",
                class_name="wispay-new-validation is-error",
            ),
            rx.fragment(),
        ),
        rx.cond(
            RequestCreateState.warnings.length() > 0,  # type: ignore[attr-defined]
            rx.el.div(
                rx.el.div(
                    rx.el.span("i", class_name="wispay-new-validation-mark"),
                    rx.el.span("Review before submitting"),
                    class_name="wispay-new-validation-title",
                ),
                rx.el.ul(
                    rx.foreach(
                        RequestCreateState.warnings,
                        lambda item: rx.el.li(item, key=item),
                    ),
                    class_name="wispay-new-error-list",
                ),
                role="status",
                class_name="wispay-new-validation is-warn",
            ),
            rx.fragment(),
        ),
        rx.el.dl(
            _summary_row("Title", RequestCreateState.title),
            _summary_row("Type", _subtype_heading()),
            _summary_row(
                "Payee",
                rx.cond(
                    RequestCreateState.payee_display != "",
                    RequestCreateState.payee_display,
                    "—",
                ),
            ),
            _summary_row(
                "Gross amount",
                rx.cond(
                    RequestCreateState.gross_preview != "",
                    RequestCreateState.gross_preview,
                    "Enter amounts to preview",
                ),
            ),
            _summary_row("Cost center", RequestCreateState.cost_center),
            _summary_row("Currency", RequestCreateState.currency),
            _summary_row(
                "Accounting period",
                rx.cond(
                    RequestCreateState.accounting_period != "",
                    RequestCreateState.accounting_period,
                    "—",
                ),
            ),
            _summary_row("Budget period", RequestCreateState.budget_period),
            class_name="wispay-new-card wispay-new-review-summary",
        ),
        rx.el.p(
            "Submitting freezes this request data for review; corrections after submission go through Return-for-correction. ",
            rx.el.strong(
                "WisPay approves and records payments; it never initiates money movement."
            ),
            class_name="wispay-new-review-note",
        ),
        class_name="wispay-new-panel",
    )


def _actions() -> rx.Component:
    return rx.el.div(
        rx.cond(
            RequestCreateState.step > 1,
            rx.el.button(
                "Back",
                type="button",
                class_name="wispay-button wispay-new-button-ghost",
                on_click=RequestCreateState.go_back,
            ),
            rx.el.span(aria_hidden="true"),
        ),
        rx.cond(
            RequestCreateState.step < 4,
            rx.el.button(
                "Continue",
                type="button",
                class_name="wispay-button wispay-button-primary",
                on_click=RequestCreateState.go_next,
            ),
            rx.el.button(
                "Submit for approval",
                type="button",
                class_name="wispay-button wispay-button-primary",
                on_click=RequestCreateState.submit,
            ),
        ),
        class_name="wispay-new-actions",
    )


def _success_panel() -> rx.Component:
    return rx.el.section(
        rx.el.p("Submitted", class_name="wispay-new-eyebrow"),
        rx.el.h2("Payment Request submitted", class_name="wispay-new-h2"),
        rx.el.p(
            "Your request entered the review lifecycle. Track progress from the queue.",
            class_name="wispay-new-muted",
        ),
        rx.el.span(
            RequestCreateState.submitted_number,
            class_name="wispay-new-num wispay-new-request-number",
        ),
        rx.el.span("Submitted", class_name="wispay-new-pill-success"),
        rx.el.div(
            rx.link(
                "View requests", href="/requests", class_name="wispay-button wispay-button-primary"
            ),
            rx.el.button(
                "Create another",
                type="button",
                class_name="wispay-button wispay-new-button-ghost",
                on_click=RequestCreateState.reset_wizard,
            ),
            class_name="wispay-new-inline-actions",
        ),
        role="status",
        class_name="wispay-new-panel wispay-new-success",
    )


def request_new_page() -> rx.Component:
    """Render the four-step create-payment-request wizard."""
    return shell(
        rx.el.div(
            rx.el.header(
                rx.el.div(
                    rx.el.p("Request intake", class_name="wispay-new-eyebrow"),
                    rx.el.h1("Create payment request", class_name="wispay-new-title"),
                    rx.el.p(
                        "Build a complete request and submit it for review.",
                        class_name="wispay-new-muted",
                    ),
                    class_name="wispay-new-header-copy",
                ),
                rx.el.span("Draft", class_name="wispay-new-draft-badge"),
                class_name="wispay-new-header",
            ),
            rx.el.div(
                RequestCreateState.status_message,
                role="status",
                class_name="wispay-new-live-status",
            ),
            _step_bar(),
            rx.cond(
                RequestCreateState.submitted_number != "",
                _success_panel(),
                rx.fragment(
                    rx.cond(
                        RequestCreateState.step == 1,
                        _step_type(),
                        rx.cond(
                            RequestCreateState.step == 2,
                            _step_details(),
                            rx.cond(
                                RequestCreateState.step == 3, _step_documents(), _step_review()
                            ),
                        ),
                    ),
                    _actions(),
                ),
            ),
            class_name="wispay-new-shell",
        )
    )
