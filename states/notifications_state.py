"""Notifications state adapter (in-app bell + recent-audit ticker).

Pure server-side state. The sample fixtures surface unread items + a
recent-audit ticker; the channel is IN_APP per ADR-0007.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import reflex as rx


@dataclass(frozen=True, slots=True)
class NotificationItem:
    """One in-app notification row."""

    notification_id: str
    when: datetime
    title: str
    body: str
    unread: bool


_FIXTURES: tuple[NotificationItem, ...] = (
    NotificationItem(
        notification_id="n-001",
        when=datetime(2026, 8, 24, 9, 0),
        title="Route generated for WPR-2026-DEMO-06",
        body="Approval Pending — first reviewer can act.",
        unread=True,
    ),
    NotificationItem(
        notification_id="n-002",
        when=datetime(2026, 8, 23, 16, 30),
        title="Payment recorded for WPR-2026-DEMO-09",
        body="External reference EXT-… recorded.",
        unread=False,
    ),
    NotificationItem(
        notification_id="n-003",
        when=datetime(2026, 8, 22, 11, 0),
        title="Over-budget exception on WPR-2026-DEMO-16",
        body="CFO appended to the route.",
        unread=True,
    ),
)


def _rows(items: tuple[NotificationItem, ...]) -> list[dict[str, str]]:
    return [
        {
            "id": item.notification_id,
            "when": item.when.strftime("%d %b %Y %H:%M"),
            "title": item.title,
            "body": item.body,
            "unread": "yes" if item.unread else "no",
        }
        for item in items
    ]


class NotificationsState(rx.State):
    """In-app notification state for the sidebar bell."""

    items: list[dict[str, str]] = _rows(_FIXTURES)
    unread_count: int = sum(1 for item in _FIXTURES if item.unread)

    @rx.event
    def mark_all_read(self) -> None:
        """Mark every notification as read (no driver access)."""

        self.items = [{**item, "unread": "no"} for item in self.items]
        self.unread_count = 0


__all__ = ["NotificationsState"]
