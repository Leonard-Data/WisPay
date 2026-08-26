"""Unit tests for the Entra ID authentication service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from WisPay.services.authentication import (
    AuthConfigError,
    AuthFlowError,
    EntraAuthService,
    EntraAuthSettings,
    InMemorySessionStore,
    PendingFlowRegistry,
    new_session,
    reset_entra_settings,
)
from WisPay.services.authentication import (
    AuthenticatedIdentity as Identity,
)


class FakeApp:
    """Scriptable stand-in for msal.ConfidentialClientApplication."""

    def __init__(self, exchange_result: dict[str, Any] | None = None) -> None:
        self.exchange_result = exchange_result or {}
        self.flow_kwargs: dict[str, Any] | None = None
        self.exchange_args: tuple[Any, ...] | None = None

    def initiate_auth_code_flow(self, **kwargs: Any) -> dict[str, Any]:
        self.flow_kwargs = kwargs
        return {
            "state": "state-abc",
            "code_verifier": "verifier-xyz",
            "auth_uri": "https://login.microsoftonline.com/t/oauth2/v2.0/authorize?p=1",
            "nonce": "nonce-1",
        }

    def acquire_token_by_auth_code_flow(
        self, flow: dict[str, Any], response: dict[str, Any]
    ) -> dict[str, Any]:
        self.exchange_args = (flow, response)
        if "error" in self.exchange_result:
            return self.exchange_result
        claims = self.exchange_result.get("id_token_claims")
        if claims is not None:
            return {**self.exchange_result, "id_token_claims": dict(claims)}
        return dict(self.exchange_result)


def make_settings(**overrides: str) -> EntraAuthSettings:
    values: dict[str, str] = {
        "tenant_id": "tenant-1",
        "client_id": "client-1",
        "client_secret": "secret-1",
    }
    values.update(overrides)
    return EntraAuthSettings(**values)  # type: ignore[arg-type]


def make_service(app: FakeApp, **settings: str) -> EntraAuthService:
    return EntraAuthService(
        settings=make_settings(**settings),
        app_factory=lambda _settings: app,
    )


def test_settings_configured_and_authority() -> None:
    assert make_settings().configured() is True
    assert make_settings().authority == "https://login.microsoftonline.com/tenant-1"
    assert make_settings(client_id="").configured() is False
    with pytest.raises(AuthConfigError):
        EntraAuthSettings(client_id="c").authority  # noqa: B018 - must raise


def test_from_env_reads_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_ENTRA_TENANT_ID", "t-env")
    monkeypatch.setenv("AZURE_ENTRA_CLIENT_ID", "c-env")
    monkeypatch.setenv("AZURE_ENTRA_CLIENT_SECRET", "s-env")
    monkeypatch.setenv("AZURE_ENTRA_REDIRECT_URI", "http://localhost:3000/auth/callback")
    try:
        settings = EntraAuthSettings.from_env()
        assert (settings.tenant_id, settings.client_id, settings.client_secret) == (
            "t-env",
            "c-env",
            "s-env",
        )
    finally:
        monkeypatch.delenv("AZURE_ENTRA_TENANT_ID", raising=False)
        monkeypatch.delenv("AZURE_ENTRA_CLIENT_ID", raising=False)
        monkeypatch.delenv("AZURE_ENTRA_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AZURE_ENTRA_REDIRECT_URI", raising=False)
        reset_entra_settings()


def test_build_url_registers_consumable_pending_flow() -> None:
    app = FakeApp()
    service = make_service(app)
    registry = PendingFlowRegistry()
    url = service.build_authorization_url(registry, redirect_to="/requests")

    assert url.startswith("https://login.microsoftonline.com/")
    assert app.flow_kwargs is not None
    assert app.flow_kwargs["redirect_uri"] == "http://localhost:3000/auth/callback"
    assert "User.Read" in app.flow_kwargs["scopes"]

    pending = registry.consume("state-abc")
    assert pending is not None
    assert pending.verifier == "verifier-xyz"
    assert pending.redirect_to == "/requests"
    assert registry.consume("state-abc") is None


def test_exchange_happy_path_maps_claims() -> None:
    app = FakeApp(
        {
            "access_token": "at",
            "id_token": "id-hint",
            "id_token_claims": {
                "oid": "oid-9",
                "preferred_username": "user@corp.example",
                "name": "Test User",
            },
        }
    )
    service = make_service(app)
    registry = PendingFlowRegistry()
    service.build_authorization_url(registry)

    result = service.exchange_code(registry, "auth-code", "state-abc")
    assert result.identity.external_identity_id == "oid-9"
    assert result.identity.email == "user@corp.example"
    assert result.identity.display_name == "Test User"
    assert result.identity.id_token_hint == "id-hint"
    assert result.redirect_to == "/"
    assert app.exchange_args is not None
    flow, response = app.exchange_args
    assert flow["code_verifier"] == "verifier-xyz"
    assert response == {"code": "auth-code", "state": "state-abc"}


def test_exchange_rejects_unknown_state() -> None:
    service = make_service(FakeApp())
    with pytest.raises(AuthFlowError):
        service.exchange_code(PendingFlowRegistry(), "code", "never-registered")


def test_exchange_maps_msal_error_to_flow_error() -> None:
    app = FakeApp({"error": "invalid_grant", "error_description": "code expired"})
    service = make_service(app)
    registry = PendingFlowRegistry()
    service.build_authorization_url(registry)
    with pytest.raises(AuthFlowError, match="invalid_grant"):
        service.exchange_code(registry, "code", "state-abc")


def test_exchange_requires_identity_claims() -> None:
    app = FakeApp({"access_token": "at", "id_token_claims": {"name": "No Id"}})
    service = make_service(app)
    registry = PendingFlowRegistry()
    service.build_authorization_url(registry)
    with pytest.raises(AuthFlowError, match="claims"):
        service.exchange_code(registry, "code", "state-abc")


def test_unconfigured_service_raises_config_error() -> None:
    service = EntraAuthService(settings=EntraAuthSettings())
    with pytest.raises(AuthConfigError):
        service.build_authorization_url(PendingFlowRegistry())


def test_logout_url_shape() -> None:
    service = make_service(FakeApp())
    url = service.build_logout_url("https://app.example/", id_token_hint="hint")
    assert url.startswith("https://login.microsoftonline.com/tenant-1/oauth2/v2.0/logout")
    assert "post_logout_redirect_uri" in url
    assert "id_token_hint" in url
    bare = service.build_logout_url("https://app.example/")
    assert "id_token_hint" not in bare


def identity(id_: str = "oid-1") -> Identity:
    return Identity(
        external_identity_id=id_,
        email="user@corp.example",
        display_name="User",
        id_token_hint=None,
    )


def test_new_session_persists_unique_records() -> None:
    store = InMemorySessionStore()
    settings = make_settings()
    first = new_session(store, identity(), settings)
    second = new_session(store, identity("oid-2"), settings)
    assert first.session_id != second.session_id
    assert store.get(first.session_id) == first


def test_sessions_expire_and_delete() -> None:
    store = InMemorySessionStore()
    settings = make_settings()
    past = datetime(2026, 1, 1, tzinfo=UTC)
    record = new_session(store, identity(), settings, clock=lambda: past)

    assert record.expired(record.created_at) is False
    assert (
        record.expired(record.created_at + timedelta(minutes=settings.session_ttl_minutes)) is True
    )
    # Lazily evicted once past its expiry.
    assert store.get(record.session_id) is None

    fresh = new_session(store, identity("oid-3"), settings)
    store.delete(fresh.session_id)
    assert store.get(fresh.session_id) is None
