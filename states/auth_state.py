"""Authentication state shared by every WisPay page state.

``AuthState`` is the base class for all application states: it owns the opaque
session cookie, the loaded user profile vars, and the sign-in / sign-out /
callback / guard event handlers. Business rules stay in
``WisPay.services.authentication`` / ``user_context``; this class only
sequences calls and translates typed outcomes into renderable state
(ADR-0005 seam).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from reflex.event import EventSpec  # noqa: TC002 - Reflex resolves handler hints at runtime

from WisPay.models import AuditAction, UserSnapshot
from WisPay.services.audit_trail import InMemoryAuditTrail, canonical_payload
from WisPay.services.authentication import (
    AuthConfigError,
    AuthFlowError,
    EntraAuthService,
    ExchangeResult,
    InMemorySessionStore,
    PendingFlowRegistry,
    SessionRecord,
    SessionStore,
    get_entra_settings,
    new_session,
)
from WisPay.services.reference_data import RETENTION_POLICY_ID_PROTOTYPE
from WisPay.services.user_context import (
    ROLE_ASSIGNMENTS,
    InMemoryUserRepository,
    UserRepository,
    active_roles,
    resolve_user,
    user_snapshot,
)

_ANONYMOUS_IDENTITY = "anonymous"


def _utcnow() -> datetime:
    """Clock used for audit timestamps and session math."""

    return datetime.now(UTC)


def get_flow_registry() -> PendingFlowRegistry:
    """Pending sign-in flows keyed by CSRF state (process-global)."""

    return _FLOW_REGISTRY


def get_session_store() -> SessionStore:
    """Server-side session store singleton."""

    return _SESSION_STORE


def get_user_repository() -> UserRepository:
    """User profile repository singleton."""

    return _USER_REPOSITORY


def get_audit_trail() -> InMemoryAuditTrail:
    """Session-scoped audit trail singleton."""

    return _AUDIT_TRAIL


def get_auth_service() -> EntraAuthService:
    """Entra ID service singleton built over cached settings."""

    return _AUTH_SERVICE


_FLOW_REGISTRY = PendingFlowRegistry()
_SESSION_STORE: SessionStore = InMemorySessionStore()
_USER_REPOSITORY: UserRepository = InMemoryUserRepository()
_AUDIT_TRAIL = InMemoryAuditTrail()
_AUTH_SERVICE = EntraAuthService()


def _anonymous_actor(now: datetime) -> UserSnapshot:
    """Actor placeholder for failed sign-ins where no identity is known."""

    return UserSnapshot(
        external_identity_id=_ANONYMOUS_IDENTITY,
        display_name="Anonymous sign-in attempt",
        email="anonymous@sign-in.invalid",
        captured_at=now,
    )


def parse_callback_params(router_data: dict[str, Any]) -> dict[str, str]:
    """Extract OIDC response parameters from the router's query dict."""

    query = router_data.get("query") or {}
    if not isinstance(query, dict):
        return {}
    return {str(key): str(value) for key, value in query.items()}


class AuthState(rx.State):
    """Base state: session cookie, current user, and authentication events."""

    session_token: str = rx.Cookie(
        "",
        name="wispay_session",
        max_age=28800,
        same_site="lax",
    )
    auth_error: str = ""

    # Populated server-side by ``guard`` / ``handle_callback``.
    _session_valid: bool = False
    current_user_name: str = ""
    current_user_email: str = ""
    current_user_roles: tuple[str, ...] = ()

    @rx.var
    def is_authenticated(self) -> bool:
        """Whether a validated server-side session backs this browser."""

        return self._session_valid and bool(self.session_token)

    @rx.event
    def start_login(self) -> EventSpec | None:
        """Redirect the browser to the Microsoft Entra ID sign-in page."""

        try:
            url = get_auth_service().build_authorization_url(get_flow_registry())
        except AuthConfigError as exc:
            self.auth_error = str(exc)
            return None
        self.auth_error = ""
        # Same-tab top-level navigation: OAuth redirects must not strand the
        # session in a popup (rx.redirect(is_external=True) opens a new tab).
        return rx.call_script(f"window.location.href = {json.dumps(url)}")

    @rx.var
    def current_roles_label(self) -> str:
        """Tooltip text describing the signed-in user's effective roles."""

        if not self.is_authenticated or not self.current_user_roles:
            return "Signed in"
        return "Roles: " + ", ".join(self.current_user_roles)

    @rx.event
    def handle_callback(self) -> EventSpec | None:
        """Complete the OIDC redirect: validate, exchange, open a session."""

        params = parse_callback_params(self.router_data)
        now = _utcnow()
        error = params.get("error")
        if error:
            description = params.get("error_description") or error
            self._audit_sign_in_failed(entity_id=params.get("state") or "n/a", now=now)
            self.auth_error = f"Microsoft sign-in did not complete ({description})."
            return rx.redirect("/login")
        code = params.get("code")
        state = params.get("state")
        if not code or not state:
            self.auth_error = "The sign-in response was missing its security parameters."
            return rx.redirect("/login")
        try:
            result: ExchangeResult = get_auth_service().exchange_code(
                get_flow_registry(), code, state
            )
            profile = resolve_user(get_user_repository(), result.identity, now)
            record = new_session(get_session_store(), result.identity, get_entra_settings())
        except (AuthConfigError, AuthFlowError) as exc:
            self._audit_sign_in_failed(entity_id=state[:16], now=now)
            self.auth_error = str(exc)
            return rx.redirect("/login")

        self.session_token = record.session_id
        self.current_user_name = profile.display_name
        self.current_user_email = profile.email
        self.current_user_roles = ()
        self._session_valid = True
        self.auth_error = ""
        self._append_audit(
            actor=user_snapshot(profile, now),
            action=AuditAction.SIGNED_IN,
            entity_id=profile.external_identity_id,
            new_value=canonical_payload({"email": profile.email}),
            now=now,
        )
        return rx.redirect(result.redirect_to or "/")

    @rx.event
    def initiate_logout(self) -> EventSpec | None:
        """Close the server-side session and clear the browser cookie."""

        token = self.session_token
        now = _utcnow()
        record: SessionRecord | None = get_session_store().get(token) if token else None
        if token:
            get_session_store().delete(token)
        self.session_token = ""
        self._reset_profile()
        if record is not None:
            self._append_audit(
                actor=_snapshot_from_record(record, now),
                action=AuditAction.SIGNED_OUT,
                entity_id=record.external_identity_id,
                new_value=None,
                now=now,
            )
        return rx.redirect("/")

    @rx.event
    def guard(self) -> EventSpec | None:
        """Page-load gate: validate the session or send the visitor to login."""

        token = self.session_token
        if not token:
            self._reset_profile()
            return rx.redirect("/login")
        now = _utcnow()
        record = get_session_store().get(token)
        if record is None:
            self._reset_profile()
            self.session_token = ""
            self.auth_error = "Your session has expired. Sign in again."
            return rx.redirect("/login")
        profile = resolve_user(get_user_repository(), record, now)
        self.current_user_name = profile.display_name
        self.current_user_email = profile.email
        self.current_user_roles = tuple(
            role.value for role in active_roles(ROLE_ASSIGNMENTS, record.external_identity_id, now)
        )
        self._session_valid = True
        self.auth_error = ""
        return None

    def _reset_profile(self) -> None:
        """Clear every loaded-identity field."""

        self._session_valid = False
        self.current_user_name = ""
        self.current_user_email = ""
        self.current_user_roles = ()

    def _audit_sign_in_failed(self, entity_id: str, now: datetime) -> None:
        """Record a failed sign-in against an anonymous actor snapshot."""

        self._append_audit(
            actor=_anonymous_actor(now),
            action=AuditAction.SIGN_IN_FAILED,
            entity_id=entity_id or "n/a",
            new_value=None,
            now=now,
        )

    def _append_audit(
        self,
        *,
        actor: UserSnapshot,
        action: AuditAction,
        entity_id: str,
        new_value: str | None,
        now: datetime,
    ) -> None:
        """Append one authentication event through the audit service boundary."""

        correlation_id = uuid.uuid4().hex
        get_audit_trail().append(
            entity_type="AuthenticationSession",
            entity_id=entity_id,
            actor=actor,
            action=action,
            occurred_at=now,
            new_value=new_value,
            correlation_id=correlation_id,
            retention_policy_id=RETENTION_POLICY_ID_PROTOTYPE,
        )


def _snapshot_from_record(record: SessionRecord, now: datetime) -> UserSnapshot:
    """Rebuild an audit actor from the stored session record."""

    return UserSnapshot(
        external_identity_id=record.external_identity_id,
        display_name=record.display_name,
        email=record.email,
        captured_at=now,
    )
