"""Details step (step 2) of the create-payment-request wizard.

Renders the adaptive form: identity fields per request family, accounting
and amount inputs with a live gross preview, and the business-purpose
narrative. Field wiring comes from ``controls``; reference options come
from ``WisPay.services.reference_data``.

Usage::

    from WisPay.pages.request_new.step_details import step_details

    rx.cond(RequestCreateState.step == 2, step_details(), ...)
"""

from __future__ import annotations

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.pages.request_new.catalogs import CURRENCY_OPTIONS
from WisPay.pages.request_new.controls import field, select, subtype_heading, text_input
from WisPay.services.reference_data import (
    COST_CENTERS,
    EXPENSE_CATEGORIES,
    LEGAL_ENTITIES,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    POLICY_CATEGORIES,
)


def vendor_identity_fields() -> rx.Component:
    """Render the vendor-payment identity fields (invoice, terms, method).

    Usage::
        rx.cond(RequestCreateState.family == "vendor", vendor_identity_fields(), ...)
    """

    return rx.fragment(
        field("Vendor", "vendor_name", text_input("vendor_name", "Supplier legal name")),
        field("Invoice number", "invoice_number", text_input("invoice_number", "INV-XXXX")),
        field("Invoice date", "invoice_date", text_input("invoice_date", input_type="date")),
        field("Payment due date", "due_date", text_input("due_date", input_type="date")),
        field(
            "Payment terms",
            "payment_terms_code",
            select(
                "payment_terms_code",
                [(o.code, o.name) for o in PAYMENT_TERMS],
                placeholder=True,
            ),
        ),
        field(
            "Proposed payment method",
            "payment_method_code",
            select(
                "payment_method_code",
                [(o.code, o.name) for o in PAYMENT_METHODS],
                placeholder=True,
            ),
        ),
    )


def employee_identity_fields() -> rx.Component:
    """Render the employee-payment identity fields per selected subtype.

    Usage::
        rx.cond(RequestCreateState.family == "vendor", ..., employee_identity_fields())
    """

    return rx.cond(
        RequestCreateState.subtype == "reimbursement",
        rx.fragment(
            field("Merchant / payee", "merchant", text_input("merchant", "Merchant name")),
            field("Expense date", "expense_date", text_input("expense_date", input_type="date")),
            field(
                "Policy category",
                "policy_category",
                select("policy_category", POLICY_CATEGORIES, placeholder=True),
            ),
        ),
        rx.cond(
            RequestCreateState.subtype == "advance",
            rx.fragment(
                field(
                    "Activity start",
                    "activity_start",
                    text_input("activity_start", input_type="date"),
                ),
                field(
                    "Activity end", "activity_end", text_input("activity_end", input_type="date")
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
                    field(
                        "Policy category",
                        "policy_category",
                        select("policy_category", POLICY_CATEGORIES, placeholder=True),
                    ),
                ),
            ),
        ),
    )


def section_head(title: str, copy: str) -> rx.Component:
    """Render one Details section heading block.

    Args:
        title: Section title.
        copy: One-line explainer under the title.

    Usage::
        section_head("Accounting & amount", "Assign the spend and confirm the amount.")
    """

    return rx.el.div(
        rx.el.h3(title),
        rx.el.p(copy, class_name="wispay-new-muted"),
        class_name="wispay-new-section-head",
    )


def gross_preview_card() -> rx.Component:
    """Render the live gross-amount preview card.

    Usage::
        gross_preview_card()
    """

    return rx.el.div(
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
    )


def purpose_field() -> rx.Component:
    """Render the business-purpose textarea field.

    Usage::
        purpose_field()
    """

    return field(
        "Purpose",
        "purpose",
        rx.el.textarea(
            id="fld-purpose",
            placeholder="Why is this expense needed?",
            value=RequestCreateState.purpose,
            on_change=RequestCreateState.set_field("purpose"),  # type: ignore[operator]
            class_name="wispay-new-input wispay-new-textarea",
        ),
    )


def step_details() -> rx.Component:
    """Render the full Details step panel for the selected request type.

    Usage::
        rx.cond(RequestCreateState.step == 2, step_details(), ...)
    """

    amount_label = rx.cond(RequestCreateState.family == "vendor", "Net amount", "Amount")
    return rx.el.section(
        rx.el.p("Step 2 · Details", class_name="wispay-new-eyebrow"),
        rx.el.h2(subtype_heading(), class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p("Required fields are checked before you continue.", class_name="wispay-new-muted"),
        rx.el.div(
            section_head("Request", "Name the request and identify who is paid."),
            rx.el.div(
                field("Request title", "title", text_input("title", "Brief descriptive title")),
                rx.cond(
                    RequestCreateState.family == "vendor",
                    vendor_identity_fields(),
                    employee_identity_fields(),
                ),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        rx.el.div(
            section_head("Accounting & amount", "Assign the spend and confirm the amount."),
            rx.el.div(
                field(
                    "Legal entity",
                    "legal_entity",
                    select(
                        "legal_entity",
                        [(o.code, o.name) for o in LEGAL_ENTITIES],
                        placeholder=True,
                    ),
                ),
                field(
                    "Cost center",
                    "cost_center",
                    select(
                        "cost_center",
                        [(o.code, o.name) for o in COST_CENTERS],
                        placeholder=True,
                    ),
                ),
                field("Project", "project", text_input("project", "PRJ-XXX"), required=False),
                field(
                    "Expense category",
                    "expense_category",
                    select(
                        "expense_category",
                        [(o.code, o.name) for o in EXPENSE_CATEGORIES],
                        placeholder=True,
                    ),
                ),
                field(
                    "Classification",
                    "classification",
                    select("classification", ("OPEX", "CAPEX")),
                ),
                field("Budget period", "budget_period", text_input("budget_period", "YYYY-MM")),
                field("Currency", "currency", select("currency", CURRENCY_OPTIONS)),
                field(amount_label, "net_text", text_input("net_text", "0", input_type="number")),
                rx.cond(
                    RequestCreateState.family == "vendor",
                    field(
                        "VAT amount", "vat_text", text_input("vat_text", "0", input_type="number")
                    ),
                    rx.fragment(),
                ),
                gross_preview_card(),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        rx.el.div(
            section_head("Business purpose", "Give reviewers enough context to decide."),
            rx.el.div(
                purpose_field(),
                class_name="wispay-new-form-grid",
            ),
            class_name="wispay-new-section",
        ),
        class_name="wispay-new-panel",
    )
