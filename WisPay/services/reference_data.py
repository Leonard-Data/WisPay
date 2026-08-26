from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from WisPay.models import (
    DocumentCategory,
    UserSnapshot,
)


@dataclass(frozen=True)
class SampleOption:
    """A code/name pair for a sample accounting or master-data option."""

    code: str
    name: str


@dataclass(frozen=True)
class DocRequirement:
    """One row of the provisional document-requirement checklist."""

    key: str
    label: str
    category: DocumentCategory
    required: bool


# Canonical currency -> decimal-scale table. VND has no minor units (scale 0);
# USD and EUR settle to two decimal places. Money parsing keys off this table.
CURRENCIES: tuple[tuple[str, int], ...] = (
    ("VND", 0),
    ("USD", 2),
    ("EUR", 2),
)

# Sample accounting dimension options surfaced by the wizard. Real values come
# from a master-data source in Phase 0; these are visibly labeled samples.
LEGAL_ENTITIES: tuple[SampleOption, ...] = (
    SampleOption(code="VN01", name="WisPay Vietnam"),
    SampleOption(code="SG01", name="WisPay Singapore"),
)
COST_CENTERS: tuple[SampleOption, ...] = (
    SampleOption(code="CC-100", name="Corporate Finance"),
    SampleOption(code="CC-200", name="Operations"),
)
EXPENSE_CATEGORIES: tuple[SampleOption, ...] = (
    SampleOption(code="SERVICES", name="Professional Services"),
    SampleOption(code="TRAVEL", name="Travel & Entertainment"),
    SampleOption(code="SUPPLIES", name="Office Supplies"),
)
PAYMENT_TERMS: tuple[SampleOption, ...] = (
    SampleOption(code="NET15", name="Net 15"),
    SampleOption(code="NET30", name="Net 30"),
    SampleOption(code="NET45", name="Net 45"),
)
PAYMENT_METHODS: tuple[SampleOption, ...] = (
    SampleOption(code="BANK_TRANSFER", name="Bank transfer"),
    SampleOption(code="CHEQUE", name="Cheque"),
)

# Policy categories drive employee reimbursement/advance classification. The
# matrix below depends on these being stable free-text buckets.
POLICY_CATEGORIES: tuple[str, ...] = (
    "Client engagement",
    "Internal training",
    "Travel",
    "Office supplies",
)

# Fixed prototype requester (decision 10): no auth yet. This snapshot is
# visibly labeled sample configuration; real identity lands with issue 05.
REQUESTER_PROTOTYPE: UserSnapshot = UserSnapshot(
    external_identity_id="entra-prototype-requester",
    display_name="Prototype Requester",
    email="requester.prototype@wispay.example",
    department="Finance",
    captured_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
)

# Fixed prototype retention policy for session-scoped audit events (decision 5).
# Real policies come from the retention configuration in Phase 1; this id only
# satisfies the AuditEvent contract until persistence lands (issue 05).
RETENTION_POLICY_ID_PROTOTYPE: UUID = UUID("00000000-0000-4000-8000-000000000001")


# The matrix below is sample configuration — not policy — pending Phase 0
# sign-off (spec decisions 4 and the provisional document-requirement table).
_DOC_MATRIX: dict[tuple[str, str], tuple[DocRequirement, ...]] = {
    ("vendor", "standard"): (
        DocRequirement(
            key="invoice",
            label="Invoice",
            category=DocumentCategory.INVOICE,
            required=True,
        ),
        DocRequirement(
            key="purchase_order",
            label="Purchase order",
            category=DocumentCategory.PURCHASE_ORDER,
            required=False,
        ),
        DocRequirement(
            key="contract",
            label="Contract",
            category=DocumentCategory.CONTRACT,
            required=False,
        ),
        DocRequirement(
            key="goods_receipt",
            label="Goods receipt",
            category=DocumentCategory.GOODS_RECEIPT,
            required=False,
        ),
        DocRequirement(
            key="service_acceptance",
            label="Service acceptance",
            category=DocumentCategory.ACCEPTANCE_RECORD,
            required=False,
        ),
    ),
    ("employee", "reimbursement"): (
        DocRequirement(
            key="receipt",
            label="Receipt",
            category=DocumentCategory.RECEIPT,
            required=True,
        ),
        DocRequirement(
            key="expense_statement",
            label="Expense statement",
            category=DocumentCategory.EXPENSE_STATEMENT,
            required=False,
        ),
    ),
    ("employee", "advance"): (
        DocRequirement(
            key="activity_evidence",
            label="Activity evidence",
            category=DocumentCategory.ACCEPTANCE_RECORD,
            required=True,
        ),
    ),
    ("employee", "settlement"): (
        DocRequirement(
            key="expense_statement",
            label="Expense statement",
            category=DocumentCategory.EXPENSE_STATEMENT,
            required=True,
        ),
    ),
    ("employee", "internal"): (
        DocRequirement(
            key="policy_approval_evidence",
            label="Policy approval evidence",
            category=DocumentCategory.ACCEPTANCE_RECORD,
            required=True,
        ),
    ),
}


def doc_requirements(family: str, subtype: str) -> tuple[DocRequirement, ...]:
    """Return the document-requirement checklist for a wizard selection.

    ``family`` is the request family (``"vendor"`` or ``"employee"``) and
    ``subtype`` is the wizard's subtype key (``"standard"`` for vendor; one of
    ``"reimbursement"``, ``"advance"``, ``"settlement"``, ``"internal"`` for
    employee). Unknown combinations return an empty tuple so callers can render
    an honest empty checklist rather than fabricating requirements.
    """

    return _DOC_MATRIX.get((family.lower(), subtype.lower()), ())
