"""Microsoft Entra ID authentication service.

Implements the OIDC Authorization Code + PKCE flow against a confidential
client (ADR-0007: corporate IdP SSO) and the opaque server-side session store.
Pure Python per ADR-0005 — this module must never import ``reflex``.

The only intended consumer is the Reflex adapter ``states/auth_state.py``,
which translates service outcomes into redirects, cookies, and UI vars.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple, Protocol, Self
from urllib.parse import urlencode
from uuid import uuid4

import msal
from pydantic import BaseModel, ConfigDict

_PENDING_FLOW_TTL_SECONDS = 600


class AuthConfigError(RuntimeError):
    """Entra ID settings are missing or incomplete."""


class AuthFlowError(RuntimeError):
    """Sign-in failed: unknown state, expired flow, or token exchange error."""


_RESERVED_OIDC_SCOPES = frozenset({"openid", "profile", "email", "offline_access"})


class EntraAuthSettings(BaseModel):
    """Configuration resolved from the environment (never hard-coded)."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:3000/auth/callback"
    scopes: tuple[str, ...] = ("openid", "profile", "email", "User.Read")
    session_ttl_minutes: int = 480

    @classmethod
    def from_env(cls) -> Self:
        """Read the ``AZURE_ENTRA_*`` variables into a frozen settings object."""

        return cls(
            tenant_id=os.environ.get("AZURE_ENTRA_TENANT_ID", ""),
            client_id=os.environ.get("AZURE_ENTRA_CLIENT_ID", ""),
            client_secret=os.environ.get("AZURE_ENTRA_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get(
                "AZURE_ENTRA_REDIRECT_URI",
                "http://localhost:3000/auth/callback",
            ),
        )

    def configured(self) -> bool:
        """Whether all values required to start a sign-in are present."""

        return bool(self.tenant_id) and bool(self.client_id) and bool(self.client_secret)

    @property
    def authority(self) -> str:
        """The Entra ID v2.0 authority URL for the configured tenant."""

        if not self.tenant_id:
            raise AuthConfigError("AZURE_ENTRA_TENANT_ID is not set.")
        return f"https://login.microsoftonline.com/{self.tenant_id}"


_SETTINGS: EntraAuthSettings | None = None


def get_entra_settings() -> EntraAuthSettings:
    """Return the cached settings, reading the environment on first use."""

    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = EntraAuthSettings.from_env()
    return _SETTINGS


def reset_entra_settings() -> None:
    """Drop the cached settings (test hook)."""

    global _SETTINGS
    _SETTINGS = None


class PendingFlow(BaseModel):
    """One in-flight sign-in: CSRF state plus its PKCE verifier."""

    model_config = ConfigDict(frozen=True)

    state: str
    verifier: str
    created_at: datetime
    redirect_to: str = "/"
    msal_flow: dict[str, Any]


class PendingFlowRegistry:
    """Thread-safe store of pending sign-in flows; each entry pops once."""

    def __init__(self, ttl_seconds: int = _PENDING_FLOW_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._flows: dict[str, PendingFlow] = {}

    def register(self, flow: PendingFlow) -> None:
        """Store a new pending flow keyed by its CSRF state value."""

        with self._lock:
            self._purge_expired_locked()
            self._flows[flow.state] = flow

    def consume(self, state: str) -> PendingFlow | None:
        """Pop the flow for ``state``; ``None`` when unknown or expired."""

        with self._lock:
            self._purge_expired_locked()
            return self._flows.pop(state, None)

    def _purge_expired_locked(self) -> None:
        cutoff = _utcnow() - timedelta(seconds=self._ttl_seconds)
        for state in [s for s, f in self._flows.items() if f.created_at < cutoff]:
            del self._flows[state]


class AuthenticatedIdentity(NamedTuple):
    """Claims extracted from a successful Entra ID token exchange."""

    external_identity_id: str
    email: str
    display_name: str
    id_token_hint: str | None


class ExchangeResult(NamedTuple):
    """Outcome of a code exchange: identity plus the originally requested page."""

    identity: AuthenticatedIdentity
    redirect_to: str


AppFactory = Callable[[EntraAuthSettings], Any]


def _default_app_factory(settings: EntraAuthSettings) -> Any:
    """Build the MSAL confidential client application."""

    return msal.ConfidentialClientApplication(
        settings.client_id,
        client_credential=settings.client_secret,
        authority=settings.authority,
    )


class EntraAuthService:
    """Drives the Entra ID authorization-code + PKCE flow via MSAL."""

    def __init__(
        self,
        settings: EntraAuthSettings | None = None,
        app_factory: AppFactory | None = None,
    ) -> None:
        self._settings = settings
        self._app_factory: AppFactory = app_factory or _default_app_factory
        self._app: Any = None

    def build_authorization_url(
        self,
        registry: PendingFlowRegistry,
        redirect_to: str = "/",
        login_hint: str | None = None,
    ) -> str:
        """Start a sign-in flow and return the Entra ID authorization URL."""

        app, settings = self._application()
        # MSAL auto-adds the OIDC-reserved scopes (openid/profile/...); passing
        # them explicitly raises ValueError, so only resource scopes go on the wire.
        resource_scopes = [
            scope for scope in settings.scopes if scope.lower() not in _RESERVED_OIDC_SCOPES
        ]
        flow = app.initiate_auth_code_flow(
            scopes=resource_scopes,
            redirect_uri=settings.redirect_uri,
            login_hint=login_hint or None,
        )
        registry.register(
            PendingFlow(
                state=flow["state"],
                verifier=flow["code_verifier"],
                created_at=_utcnow(),
                redirect_to=redirect_to or "/",
                msal_flow=flow,
            )
        )
        return flow["auth_uri"]

    def exchange_code(
        self,
        registry: PendingFlowRegistry,
        code: str,
        state: str,
    ) -> ExchangeResult:
        """Exchange an authorization code for identity claims.

        The pending flow is consumed exactly once; MSAL validates the response
        state against the stored flow (CSRF protection) before redeeming the
        PKCE verifier.
        """

        pending = registry.consume(state)
        if pending is None:
            raise AuthFlowError("Unknown, expired, or already-used sign-in flow. Start again.")
        app, _ = self._application()
        try:
            result = app.acquire_token_by_auth_code_flow(
                pending.msal_flow,
                {"code": code, "state": state},
            )
        except ValueError as exc:
            raise AuthFlowError(f"Sign-in response rejected: {exc}") from exc
        if "error" in result:
            code = result.get("error", "unknown_error")
            description = result.get("error_description") or code
            raise AuthFlowError(f"{code}: {description}")
        claims: dict[str, Any] = result.get("id_token_claims") or {}
        identity_id = claims.get("oid") or claims.get("sub") or ""
        email = claims.get("preferred_username") or claims.get("email") or ""
        display_name = claims.get("name") or email
        if not identity_id or not email:
            raise AuthFlowError("The sign-in token is missing required identity claims.")
        identity = AuthenticatedIdentity(
            external_identity_id=identity_id,
            email=email,
            display_name=display_name,
            id_token_hint=result.get("id_token"),
        )
        return ExchangeResult(identity=identity, redirect_to=pending.redirect_to)

    def build_logout_url(
        self,
        post_logout_redirect_uri: str,
        id_token_hint: str | None = None,
    ) -> str:
        """Build the Entra ID end-session URL for single-logout round trips."""

        settings = self._settings or get_entra_settings()
        params: dict[str, str] = {"post_logout_redirect_uri": post_logout_redirect_uri}
        if id_token_hint:
            params["id_token_hint"] = id_token_hint
        return f"{settings.authority}/oauth2/v2.0/logout?{urlencode(params)}"

    def _application(self) -> tuple[Any, EntraAuthSettings]:
        settings = self._settings or get_entra_settings()
        if not settings.configured():
            raise AuthConfigError(
                "Single sign-on is not configured. Set AZURE_ENTRA_TENANT_ID, "
                "AZURE_ENTRA_CLIENT_ID, and AZURE_ENTRA_CLIENT_SECRET."
            )
        if self._app is None:
            self._app = self._app_factory(settings)
        return self._app, settings


class SessionRecord(BaseModel):
    """Opaque server-side session; the browser only ever sees ``session_id``."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    external_identity_id: str
    email: str
    display_name: str
    id_token_hint: str | None = None
    created_at: datetime
    expires_at: datetime

    def expired(self, now: datetime) -> bool:
        """Whether the session is no longer valid at ``now``."""

        return now >= self.expires_at


class SessionStore(Protocol):
    """Persistence boundary for sessions; swap for Azure SQL later."""

    def create(self, record: SessionRecord) -> None: ...

    def get(self, session_id: str) -> SessionRecord | None: ...

    def delete(self, session_id: str) -> None: ...


class InMemorySessionStore(SessionStore):
    """Thread-safe process-local session store for the MVP slice."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, record: SessionRecord) -> None:
        with self._lock:
            self._sessions[record.session_id] = record

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(session_id)
        if record is None:
            return None
        if record.expired(_utcnow()):
            self.delete(session_id)
            return None
        return record

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


def new_session(
    store: SessionStore,
    identity: AuthenticatedIdentity,
    settings: EntraAuthSettings,
    clock: Callable[[], datetime] | None = None,
) -> SessionRecord:
    """Create, persist, and return a fresh session for ``identity``."""

    now = (clock or _utcnow)()
    record = SessionRecord(
        session_id=uuid4().hex,
        external_identity_id=identity.external_identity_id,
        email=identity.email,
        display_name=identity.display_name,
        id_token_hint=identity.id_token_hint,
        created_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
    )
    store.create(record)
    return record


def _utcnow() -> datetime:
    return datetime.now(UTC)
