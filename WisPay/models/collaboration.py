from __future__ import annotations

from uuid import UUID

from ._base import AwareDateTime, NonEmptyStr, WisPayBaseModel
from .enums import CommentVisibility, NotificationChannel, NotificationStatus
from .references import UserSnapshot


class Comment(WisPayBaseModel):
    comment_id: UUID
    request_id: UUID
    author: UserSnapshot
    visibility: CommentVisibility
    body: NonEmptyStr
    created_at: AwareDateTime
    mentioned_users: tuple[UserSnapshot, ...] = ()
    lifecycle_action: NonEmptyStr | None = None
    document_id: UUID | None = None


class Notification(WisPayBaseModel):
    notification_id: UUID
    event_type: NonEmptyStr
    recipient: UserSnapshot
    channel: NotificationChannel
    template_version: NonEmptyStr
    status: NotificationStatus
    retry_count: int = 0
    related_request_id: UUID | None = None
    related_action: NonEmptyStr | None = None
    created_at: AwareDateTime
    delivered_at: AwareDateTime | None = None
    last_error: NonEmptyStr | None = None
