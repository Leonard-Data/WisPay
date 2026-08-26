"""Access-request state adapter for ``/signup``.

UI adapter per ADR-0005/ADR-0007: validation and recording of Pending
access requests live in ``WisPay.services.user_context``; this class only
holds form values and sequences the submit call. Identity creation stays
with Entra ID; activation and role assignment are administrative actions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import reflex as rx

from WisPay.services.user_context import (
    get_access_request_repository,
    submit_access_request,
)


def _utcnow() -> datetime:
    """Clock for access-request submission timestamps."""

    return datetime.now(UTC)


class AccessRequestState(rx.State):
    """UI adapter for the access-request form on /signup."""

    email: str = ""
    full_name: str = ""
    business_unit: str = ""
    justification: str = ""
    form_error: str = ""
    submitted: bool = False

    @rx.event
    def set_email(self, value: str) -> None:
        """Record the work-email field value."""

        self.email = value

    @rx.event
    def set_full_name(self, value: str) -> None:
        """Record the full-name field value."""

        self.full_name = value

    @rx.event
    def set_business_unit(self, value: str) -> None:
        """Record the business-unit field value."""

        self.business_unit = value

    @rx.event
    def set_justification(self, value: str) -> None:
        """Record the justification field value."""

        self.justification = value

    @rx.event
    def submit_request(self) -> None:
        """Validate and record the access request through the service."""

        self.form_error = ""
        try:
            submit_access_request(
                get_access_request_repository(),
                email=self.email,
                display_name=self.full_name,
                business_unit=self.business_unit,
                justification=self.justification,
                now=_utcnow(),
            )
        except ValueError as exc:
            self.form_error = str(exc)
            return
        self.submitted = True
