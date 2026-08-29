"""Sample report fixtures for the /reports page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpendBar:
    """One horizontal spend bar row."""

    label: str
    value: str
    percent: int


_SPEND_BY_COST_CENTER: tuple[SpendBar, ...] = (
    SpendBar("CC-OPS-01 Operations", "VND 1,240,000,000", 100),
    SpendBar("CC-FIN-04 Finance", "VND 612,000,000", 49),
    SpendBar("CC-IT-22 Information Tech", "VND 480,000,000", 38),
    SpendBar("CC-MKT-09 Marketing", "VND 312,000,000", 25),
    SpendBar("CC-HR-03 People", "VND 198,000,000", 16),
)
SPEND_BY_COST_CENTER: list[SpendBar] = list(_SPEND_BY_COST_CENTER)


_SPEND_BY_FAMILY: tuple[SpendBar, ...] = (
    SpendBar("Vendor / standard", "VND 2,180,000,000", 100),
    SpendBar("Employee / Reimbursement", "VND 312,000,000", 14),
    SpendBar("Employee / Advance", "VND 96,000,000", 4),
    SpendBar("Employee / Internal expenditure", "VND 18,000,000", 1),
)
SPEND_BY_FAMILY: list[SpendBar] = list(_SPEND_BY_FAMILY)


_SPEND_BY_PERIOD: tuple[tuple[str, str, str], ...] = (
    ("Mar 2026", "VND 410,000,000", "+6%"),
    ("Apr 2026", "VND 528,000,000", "+29%"),
    ("May 2026", "VND 612,000,000", "+16%"),
    ("Jun 2026", "VND 488,000,000", "−20%"),
    ("Jul 2026", "VND 596,000,000", "+22%"),
    ("Aug 2026", "VND 714,000,000", "+20%"),
)
SPEND_BY_PERIOD: list[tuple[str, str, str]] = list(_SPEND_BY_PERIOD)


_EXPORT_CENTERS: tuple[tuple[str, str], ...] = (
    ("My requests (CSV)", "Requester scope"),
    ("Approvals log (CSV)", "Approver scope"),
    ("Payment records (CSV)", "Finance scope"),
    ("Audit events (CSV)", "Auditor scope"),
    ("Spend by cost center (CSV)", "Finance scope"),
    ("Spend by family (CSV)", "Finance scope"),
)
EXPORT_CENTERS: list[tuple[str, str]] = list(_EXPORT_CENTERS)


__all__ = [
    "EXPORT_CENTERS",
    "SPEND_BY_COST_CENTER",
    "SPEND_BY_FAMILY",
    "SPEND_BY_PERIOD",
    "SpendBar",
]
