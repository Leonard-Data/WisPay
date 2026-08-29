"""Sample Finance Review bucket fixtures.

Holds deterministic sample rows for each of the four Finance Review queues
until the persistent FinanceReviewService lands in t5. Every row maps to a
canonical lifecycle bucket and carries the same shape the real service
will emit (id, payee, subtype, amount display, stage label, and exception
flags) so swapping in ``FinanceReviewState.queue_rows`` in t5 is a one-liner.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinanceReviewRow:
    """One review-queue row (renderable dict-friendly)."""

    number: str
    payee: str
    subtype: str
    amount_display: str
    stage_label: str
    is_exception: bool = False
    is_passed: bool = False
    is_returned: bool = False


_BUDGET_BUCKET: tuple[FinanceReviewRow, ...] = (
    FinanceReviewRow(
        number="WPR-2026-0007",
        payee="Halcom Vietnam Co., Ltd.",
        subtype="Vendor / standard",
        amount_display="VND 142,500,000",
        stage_label="Within Budget",
        is_passed=True,
    ),
    FinanceReviewRow(
        number="WPR-2026-0011",
        payee="North Logistics JSC",
        subtype="Vendor / standard",
        amount_display="VND 312,800,000",
        stage_label="Over Budget — Exception Required",
        is_exception=True,
    ),
)
BUDGET_BUCKET: list[FinanceReviewRow] = list(_BUDGET_BUCKET)


_COMPLIANCE_BUCKET: tuple[FinanceReviewRow, ...] = (
    FinanceReviewRow(
        number="WPR-2026-0014",
        payee="Sai Gon Office Supply",
        subtype="Vendor / standard",
        amount_display="VND 12,800,000",
        stage_label="N/A — Recurring",
        is_passed=True,
    ),
    FinanceReviewRow(
        number="WPR-2026-0019",
        payee="Internal: Travel & Expense",
        subtype="Employee / Reimbursement",
        amount_display="USD 920.00",
        stage_label="Returned — Missing receipt",
        is_returned=True,
    ),
)
COMPLIANCE_BUCKET: list[FinanceReviewRow] = list(_COMPLIANCE_BUCKET)


_EVIDENCE_BUCKET: tuple[FinanceReviewRow, ...] = (
    FinanceReviewRow(
        number="WPR-2026-0023",
        payee="Da Nang Print Co.",
        subtype="Vendor / standard",
        amount_display="VND 78,400,000",
        stage_label="Matched (98%)",
        is_passed=True,
    ),
    FinanceReviewRow(
        number="WPR-2026-0027",
        payee="Mekong Freight",
        subtype="Vendor / standard",
        amount_display="VND 56,200,000",
        stage_label="Duplicate warning",
        is_exception=True,
    ),
)
EVIDENCE_BUCKET: list[FinanceReviewRow] = list(_EVIDENCE_BUCKET)


_APPROVAL_BUCKET: tuple[FinanceReviewRow, ...] = (
    FinanceReviewRow(
        number="WPR-2026-0031",
        payee="Hai Phong Steel",
        subtype="Vendor / standard",
        amount_display="VND 1,240,000,000",
        stage_label="Awaiting CFO append",
        is_exception=True,
    ),
    FinanceReviewRow(
        number="WPR-2026-0035",
        payee="HCMC Cleaning Service",
        subtype="Vendor / standard",
        amount_display="VND 18,900,000",
        stage_label="Awaiting Line Manager",
    ),
)
APPROVAL_BUCKET: list[FinanceReviewRow] = list(_APPROVAL_BUCKET)


__all__ = [
    "APPROVAL_BUCKET",
    "BUDGET_BUCKET",
    "COMPLIANCE_BUCKET",
    "EVIDENCE_BUCKET",
    "FinanceReviewRow",
]
