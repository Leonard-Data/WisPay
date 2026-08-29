"""Router integration tests for the t5 wiring.

Verifies that the new state classes are registered and that the
``WISPAY_DEMO_MODE=1`` env path triggers the seed loader.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from WisPay.routers import ROUTES, register_routes
from WisPay.services.demo_seed import demo_seed_active


def test_demo_seed_active_uses_env() -> None:
    """Env-gated activation matches the contract from §3.5 of t5."""

    saved = os.environ.pop("WISPAY_DEMO_MODE", None)
    try:
        os.environ["WISPAY_DEMO_MODE"] = "1"
        assert demo_seed_active() is True
    finally:
        os.environ.pop("WISPAY_DEMO_MODE", None)
        if saved is not None:
            os.environ["WISPAY_DEMO_MODE"] = saved


def test_routes_cover_every_product_surface() -> None:
    """Every t4 product surface is registered with a Route entry."""

    paths = {route.route for route in ROUTES}
    assert "/" in paths
    assert "/requests" in paths
    assert "/requests/[number]" in paths
    assert "/requests/new" in paths
    assert "/approvals" in paths
    assert "/finance-review" in paths
    assert "/payments" in paths
    assert "/admin" in paths
    assert "/audit" in paths
    assert "/reports" in paths
    assert "/login" in paths
    assert "/signup" in paths
    assert "/auth/callback" in paths
    assert "/logout" in paths
    assert "/404" in paths
    assert "/500" in paths
    assert "/503" in paths


def test_routes_with_on_load_have_a_guard_hook() -> None:
    """Guarded routes run ``AuthState.guard`` before any state hydration."""

    guarded = {
        "/",
        "/requests",
        "/approvals",
        "/finance-review",
        "/payments",
        "/admin",
        "/audit",
        "/reports",
    }
    for route in ROUTES:
        if route.route in guarded:
            assert route.on_load is not None
            names = [getattr(handler, "__name__", str(handler)) for handler in route.on_load]
            assert any("guard" in name for name in names), f"Guard missing on {route.route}"


def test_register_routes_is_idempotent_with_demo_mode() -> None:
    """``register_routes`` runs the demo seed when ``WISPAY_DEMO_MODE=1``."""

    saved = os.environ.pop("WISPAY_DEMO_MODE", None)
    saved_ran = os.environ.pop("WISPAY_DEMO_SEED_RAN", None)
    try:
        os.environ["WISPAY_DEMO_MODE"] = "1"
        os.environ.pop("WISPAY_DEMO_SEED_RAN", None)

        class _StubApp:
            def add_page(self, *_args: object, **_kwargs: object) -> None:
                return None

        called = {"count": 0}

        def _fake_seed(_bundle: object) -> object:
            called["count"] += 1
            return type("S", (), {"requests": 16, "audits": 0, "payments": 0, "personas": 8})()

        with (
            patch("WisPay.routers._runtime.stores") as stores_mock,
            patch("WisPay.routers.seed_demo_state", side_effect=_fake_seed),
        ):
            stores_mock.return_value = object()
            register_routes(_StubApp())  # type: ignore[arg-type]
            # Second call should not re-seed (idempotent guard).
            register_routes(_StubApp())  # type: ignore[arg-type]
            assert called["count"] == 1
            assert os.environ.get("WISPAY_DEMO_SEED_RAN") == "1"
    finally:
        os.environ.pop("WISPAY_DEMO_MODE", None)
        os.environ.pop("WISPAY_DEMO_SEED_RAN", None)
        if saved is not None:
            os.environ["WISPAY_DEMO_MODE"] = saved
        if saved_ran is not None:
            os.environ["WISPAY_DEMO_SEED_RAN"] = saved_ran
