"""Sample configuration fixtures for the admin page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThresholdRow:
    """One approval threshold matrix row."""

    role: str
    up_to: str
    fallback: str
    version: str


_THRESHOLD_ROWS: tuple[ThresholdRow, ...] = (
    ThresholdRow("Line Manager", "VND 50,000,000", "—", "v1"),
    ThresholdRow("Budget Owner", "VND 250,000,000", "Finance Reviewer", "v1"),
    ThresholdRow("Finance Reviewer / AP", "VND 1,000,000,000", "CFO append", "v1"),
    ThresholdRow("CFO / Executive Approver", "Unlimited", "—", "v1"),
)
THRESHOLD_ROWS: list[ThresholdRow] = list(_THRESHOLD_ROWS)


_PERSONA_GRID: tuple[tuple[str, str], ...] = (
    ("Requester", "Submits requests; never approves own."),
    ("Line Manager", "First approver under VND 50M."),
    ("Budget Owner", "Confirms within-budget status."),
    ("Finance Reviewer / AP", "Compliance, evidence, payment recording."),
    ("CFO / Executive Approver", "Approves over budget and largest amounts."),
    ("Payment Operator", "Records external payment completion."),
    ("System Administrator", "Configures rule sets, personas, and audits."),
    ("Auditor / Read-only Reviewer", "Read-only access to the audit stream."),
)
PERSONA_GRID: list[tuple[str, str]] = list(_PERSONA_GRID)


_DOCUMENT_REQUIREMENTS: tuple[dict[str, str], ...] = (
    {
        "family": "Vendor / standard",
        "required": "Invoice",
        "optional": "PO, Contract, Goods receipt, Acceptance",
        "version": "v1",
    },
    {
        "family": "Employee / Reimbursement",
        "required": "Receipt",
        "optional": "Expense statement",
        "version": "v1",
    },
    {
        "family": "Employee / Advance",
        "required": "Activity evidence",
        "optional": "—",
        "version": "v1",
    },
    {
        "family": "Employee / Advance settlement",
        "required": "Expense statement",
        "optional": "—",
        "version": "v1",
    },
    {
        "family": "Employee / Internal expenditure",
        "required": "Policy approval evidence",
        "optional": "—",
        "version": "v1",
    },
)
DOCUMENT_REQUIREMENTS: list[dict[str, str]] = list(_DOCUMENT_REQUIREMENTS)


__all__ = [
    "DOCUMENT_REQUIREMENTS",
    "PERSONA_GRID",
    "THRESHOLD_ROWS",
    "ThresholdRow",
]
