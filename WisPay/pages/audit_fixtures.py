"""Sample audit fixture rows for the /audit page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditRow:
    """One audit stream row (renderable dict-friendly)."""

    when: str
    action: str
    actor: str
    scope: str


_AUDIT_ROWS: tuple[AuditRow, ...] = (
    AuditRow("08:14 UTC", "Submitted", "alice@contoso.com", "WPR-2026-0041"),
    AuditRow("08:22 UTC", "Reviewed", "bob@contoso.com", "WPR-2026-0041 / Budget"),
    AuditRow("08:35 UTC", "Exception Recorded", "carol@contoso.com", "WPR-2026-0011"),
    AuditRow("09:02 UTC", "Approved", "dave@contoso.com", "WPR-2026-0035"),
    AuditRow("09:18 UTC", "Returned", "erin@contoso.com", "WPR-2026-0019"),
    AuditRow("09:47 UTC", "Changed", "alice@contoso.com", "WPR-2026-0011 / Amount"),
    AuditRow("10:11 UTC", "Payment Updated", "frank@contoso.com", "WPR-2026-0043"),
    AuditRow("10:42 UTC", "Cancelled", "alice@contoso.com", "WPR-2026-0027"),
    AuditRow("11:09 UTC", "Exported", "gina@contoso.com", "Audit CSV (Finance scope)"),
)
AUDIT_ROWS: list[AuditRow] = list(_AUDIT_ROWS)


__all__ = ["AUDIT_ROWS", "AuditRow"]
