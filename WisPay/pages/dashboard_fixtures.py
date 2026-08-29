"""Sample dashboard fixtures for the / page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DashboardKpi:
    """One dashboard KPI tile."""

    label: str
    value: str
    meta: str


_DASHBOARD_KPIS: tuple[DashboardKpi, ...] = (
    DashboardKpi("Awaiting my action", "5", "Across all queues"),
    DashboardKpi("Open in review", "12", "Finance Review queues"),
    DashboardKpi("Approved · ready to start", "3", "Operator queue"),
    DashboardKpi("Overdue", "1", "Sample fixtures"),
)
DASHBOARD_KPIS: list[DashboardKpi] = list(_DASHBOARD_KPIS)


_DASHBOARD_ACTIVITY: tuple[dict[str, str], ...] = (
    {
        "when": "08:14 UTC",
        "action": "Submitted",
        "subject": "WPR-2026-0041",
        "actor": "alice@contoso.com",
    },
    {
        "when": "08:22 UTC",
        "action": "Reviewed",
        "subject": "WPR-2026-0041 · Budget",
        "actor": "bob@contoso.com",
    },
    {
        "when": "08:35 UTC",
        "action": "Exception recorded",
        "subject": "WPR-2026-0011",
        "actor": "carol@contoso.com",
    },
    {
        "when": "09:02 UTC",
        "action": "Approved",
        "subject": "WPR-2026-0035",
        "actor": "dave@contoso.com",
    },
    {
        "when": "10:11 UTC",
        "action": "Payment recorded",
        "subject": "WPR-2026-0043",
        "actor": "frank@contoso.com",
    },
)
DASHBOARD_ACTIVITY: list[dict[str, str]] = list(_DASHBOARD_ACTIVITY)


__all__ = ["DASHBOARD_ACTIVITY", "DASHBOARD_KPIS", "DashboardKpi"]
