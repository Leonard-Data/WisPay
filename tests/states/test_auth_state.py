"""Unit tests for the AuthState base state and its handlers.

Service collaborators are stubbed at the module-singleton level so these tests
never touch MSAL or real repositories.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import states.auth_state as auth_module
from states.auth_state import (
    AuthState,
    PendingFlowRegistry,
    parse_callback_params,
)
from WisPay.services.authentication import (
    EntraAuthSettings,
    ExchangeResult,
    InMemorySessionStore,
    new_session,
)
from WisPay.services.user_context import InMemoryUserRepository

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class FakeAuthService:
    """Scriptable stand-in for EntraAuthService."""

    def __init__(
        self,
        result: ExchangeResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.url = "https://login.microsoftonline.com/t/oauth2/v2.0/authorize?x=1"

    def build_authorization_url(self, registry: Any, **kwargs: Any) -> str:
        return self.url

    def exchange_code(self, registry: Any, code: str, state: str) -> ExchangeResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def identity_result(redirect_to: str = "/") -> ExchangeResult:
    from WisPay.services.authentication import AuthenticatedIdentity

    return ExchangeResult(
        identity=AuthenticatedIdentity(
            external_identity_id="oid-1",
            email="user@corp.example",
            display_name="User One",
            id_token_hint="hint",
        ),
        redirect_to=redirect_to,
    )


@pytest.fixture()
def fresh_state(monkeypatch: pytest.MonkeyPatch) -> AuthState:
    """AuthState wired to clean in-memory collaborators."""

    monkeypatch.setattr(auth_module, "_FLOW_REGISTRY", PendingFlowRegistry())
    monkeypatch.setattr(auth_module, "_SESSION_STORE", InMemorySessionStore())
    monkeypatch.setattr(auth_module, "_USER_REPOSITORY", InMemoryUserRepository())
    settings = EntraAuthSettings(tenant_id="t", client_id="c", client_secret="s")
    monkeypatch.setattr(auth_module, "get_entra_settings", lambda: settings)
    return AuthState()


def test_parse_callback_params_handles_missing_query() -> None:
    assert parse_callback_params({}) == {}
    assert parse_callback_params({"query": {"code": "c", "state": "s"}}) == {
        "code": "c",
        "state": "s",
    }
    assert parse_callback_params({"query": None}) == {}


def test_guard_redirects_anonymous(fresh_state: AuthState) -> None:
    outcome = fresh_state.guard()
    assert outcome is not None
    assert "/login" in str(outcome)


def test_guard_accepts_valid_session(fresh_state: AuthState) -> None:
    record = new_session(
        auth_module.get_session_store(),
        identity_result().identity,
        EntraAuthSettings(tenant_id="t"),
        clock=lambda: datetime.now(UTC),
    )
    fresh_state.session_token = record.session_id
    assert fresh_state.guard() is None
    assert fresh_state.is_authenticated is True
    assert fresh_state.current_user_email == "user@corp.example"


def test_guard_clears_expired_session(fresh_state: AuthState) -> None:
    record = new_session(
        auth_module.get_session_store(),
        identity_result().identity,
        EntraAuthSettings(tenant_id="t"),
        clock=lambda: NOW - timedelta(days=2),
    )
    fresh_state.session_token = record.session_id
    outcome = fresh_state.guard()
    assert outcome is not None
    assert fresh_state.is_authenticated is False
    assert fresh_state.session_token == ""
    assert "expired" in fresh_state.auth_error.lower()


def test_start_login_redirects_to_entra(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_module, "_AUTH_SERVICE", FakeAuthService())
    outcome = fresh_state.start_login()
    assert "authorize" in str(outcome)


def test_start_login_surfaces_configuration_error(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    from WisPay.services.authentication import AuthConfigError

    class BrokenService(FakeAuthService):
        def build_authorization_url(self, registry: Any, **kwargs: Any) -> str:
            raise AuthConfigError("SSO is not configured.")

    monkeypatch.setattr(auth_module, "_AUTH_SERVICE", BrokenService())
    assert fresh_state.start_login() is None
    assert "not configured" in fresh_state.auth_error.lower()


def test_callback_success_opens_session_and_audits(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        auth_module, "_AUTH_SERVICE", FakeAuthService(result=identity_result("/requests"))
    )
    fresh_state.router_data = {"query": {"code": "c", "state": "s"}}
    outcome = fresh_state.handle_callback()

    assert outcome is not None
    assert fresh_state.is_authenticated is True
    assert fresh_state.current_user_name == "User One"
    assert fresh_state.session_token != ""
    events = auth_module.get_audit_trail().events()
    assert any(e.action.value == "Signed In" for e in events)


def test_callback_error_param_redirects_with_message(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_module, "_AUTH_SERVICE", FakeAuthService())
    fresh_state.router_data = {"query": {"error": "access_denied"}}
    outcome = fresh_state.handle_callback()
    assert outcome is not None
    assert fresh_state.auth_error.startswith("Microsoft sign-in did not complete")
    assert fresh_state.is_authenticated is False
    trail_events = auth_module.get_audit_trail().events()
    assert any(e.action.value == "Sign-in Failed" for e in trail_events)


def test_callback_flow_error_surfaces_auth_error(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    from WisPay.services.authentication import AuthFlowError

    broken = FakeAuthService(error=AuthFlowError("Unknown flow."))
    monkeypatch.setattr(auth_module, "_AUTH_SERVICE", broken)
    fresh_state.router_data = {"query": {"code": "c", "state": "bad"}}
    outcome = fresh_state.handle_callback()
    assert outcome is not None
    assert "Unknown flow" in fresh_state.auth_error


def test_logout_clears_session_and_audits(
    fresh_state: AuthState, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeAuthService(result=identity_result())
    monkeypatch.setattr(auth_module, "_AUTH_SERVICE", service)
    fresh_state.router_data = {"query": {"code": "c", "state": "s"}}
    fresh_state.handle_callback()
    token = fresh_state.session_token

    outcome = fresh_state.initiate_logout()
    assert outcome is not None
    assert fresh_state.is_authenticated is False
    assert fresh_state.session_token == ""
    assert auth_module.get_session_store().get(token) is None
    events = auth_module.get_audit_trail().events()
    assert any(e.action.value == "Signed Out" for e in events)
