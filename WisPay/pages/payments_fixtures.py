"""Sample payment queue fixtures used by the /payments page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaymentRow:
    """One payment queue row."""

    number: str
    payee: str
    subtype: str
    amount_display: str
    stage: str
    stage_label: str


_PAYMENT_BUCKET: tuple[PaymentRow, ...] = (
    PaymentRow(
        number="WPR-2026-0041",
        payee="Hai Phong Steel",
        subtype="Vendor / standard",
        amount_display="VND 1,240,000,000",
        stage="approved",
        stage_label="Approved",
    ),
    PaymentRow(
        number="WPR-2026-0043",
        payee="Da Nang Print Co.",
        subtype="Vendor / standard",
        amount_display="VND 78,400,000",
        stage="in_process",
        stage_label="Payment in Process",
    ),
    PaymentRow(
        number="WPR-2026-0045",
        payee="Mekong Freight",
        subtype="Vendor / standard",
        amount_display="VND 56,200,000",
        stage="paid",
        stage_label="Paid",
    ),
    PaymentRow(
        number="WPR-2026-0047",
        payee="Sai Gon Office Supply",
        subtype="Vendor / standard",
        amount_display="VND 12,800,000",
        stage="closure_due",
        stage_label="Closure due",
    ),
)
PAYMENT_BUCKET: list[PaymentRow] = list(_PAYMENT_BUCKET)


__all__ = ["PAYMENT_BUCKET", "PaymentRow"]
