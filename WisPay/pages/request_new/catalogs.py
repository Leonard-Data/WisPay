"""Static option catalogs for the create-payment-request wizard.

Pure data: step labels, request-type families and copy, currency options,
and the document-slot checklist. Renderers live in ``controls``/``step_*``;
this module never touches Reflex state.

Usage::

    from WisPay.pages.request_new.catalogs import DOC_SLOTS, EMPLOYEE_TYPES
"""

from __future__ import annotations

STEPS: tuple[str, ...] = ("Type", "Details", "Documents", "Review")
"""Wizard step labels shown in the progress bar."""

EMPLOYEE_TYPES: tuple[tuple[str, str], ...] = (
    ("reimbursement", "Reimbursement"),
    ("advance", "Cash advance"),
    ("settlement", "Advance settlement"),
    ("internal", "Internal expenditure"),
)
"""Employee Payment Request subtypes offered on the Type step."""

TYPE_COPY: dict[str, str] = {
    "standard": "Pay an invoice from a supplier or service provider.",
    "reimbursement": "Repay an employee for approved out-of-pocket spend.",
    "advance": "Release funds before an approved activity begins.",
    "settlement": "Reconcile actual expenses against an open advance.",
    "internal": "Record approved spend that does not use a vendor invoice.",
}
"""One-line explainer per request subtype on the selection cards."""

CURRENCY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("VND", "VND ₫"),
    ("USD", "USD $"),
    ("EUR", "EUR €"),
)
"""Currency codes offered on the Details step."""

DOC_SLOTS: tuple[tuple[str, str], ...] = (
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
"""Known document slots; visibility per request type tracks the matrix."""
